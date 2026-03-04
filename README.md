# PyCosim 架构设计文档

> Multi-FMU Co-Simulation Engine for Python
> 基于 DACCOSIM NG (Java) 架构，用 Python 复刻的多 FMU 联合仿真引擎。
> 支持 FMI 1.0/2.0/3.0，固定/动态步长，代数环求解，多核并行，ZeroMQ 多节点分布式仿真。

---

## 目录

- [1. 系统总览](#1-系统总览)
- [2. 四层架构](#2-四层架构)
- [3. 核心执行流程](#3-核心执行流程)
- [4. 数据模型设计](#4-数据模型设计)
- [5. 引擎层详细设计](#5-引擎层详细设计)
- [6. 分布式架构](#6-分布式架构)
- [7. 配置规范](#7-配置规范)
- [8. CLI 接口](#8-cli-接口)
- [9. 关键设计决策](#9-关键设计决策)
- [10. 项目结构](#10-项目结构)
- [11. 依赖与环境](#11-依赖与环境)
- [12. 测试策略](#12-测试策略)
- [13. 使用示例](#13-使用示例)

---

## 1. 系统总览

PyCosim 是一个面向 FMI（Functional Mock-up Interface）标准的多模型联合仿真引擎。它将多个 FMU（Functional Mock-up Unit）组织为有向图（Graph），通过统一的生命周期管理、变量交换和时间步进策略，实现多物理域耦合仿真。

**核心能力：**

| 能力 | 说明 |
|------|------|
| 多 FMU 联合仿真 | 任意数量 FMU 通过有向箭头（Arrow）连接 |
| 固定/自适应步长 | ConstantStepper / EulerStepper / AdamsBashforthStepper |
| 代数环求解 | Tarjan SCC 检测 + Newton-Raphson 迭代 |
| 多核并行 | ThreadPoolExecutor + BSP 屏障同步 |
| 分布式仿真 | ZeroMQ REQ/REP 协议，Stub/Soul 代理模式 |
| 数学运算节点 | Adder / Multiplier / Gain / Offset |
| CSV 数据导出 | 可选变量、可配置导出路径 |

---

## 2. 四层架构

```
┌─────────────────────────────────────────────────────────────┐
│  CLI Layer  (cli.py, __main__.py)                           │
│  入口层：命令行解析，启动协调器或工作节点                         │
├─────────────────────────────────────────────────────────────┤
│  Config Layer  (config/)                                    │
│  配置层：JSON 解析，Builder 模式构建仿真图                      │
│  load_graph() → Graph                                       │
├─────────────────────────────────────────────────────────────┤
│  Model Layer  (model/)                                      │
│  模型层：不可变运行时数据结构                                    │
│  Graph, GraphNode, Arrow, Variable, FMUProxy                │
├─────────────────────────────────────────────────────────────┤
│  Engine Layer  (engine/)                                    │
│  执行层：仿真生命周期编排                                       │
│  GraphExecutor, Iterator, CoInitializer, Exporter, Stepper  │
├─────────────────────────────────────────────────────────────┤
│  Distributed Layer  (distributed/)                          │
│  分布式层：ZeroMQ 通信                                        │
│  FMUStub / FMUSoul, Protocol, Worker                        │
└─────────────────────────────────────────────────────────────┘
```

**层间依赖关系：**

- CLI → Config → Model（构建 Graph）
- CLI → Engine（执行 Graph）
- Engine → Model（操作节点与箭头）
- Distributed → Model（远程节点代理）

---

## 3. 核心执行流程

### 3.1 四阶段生命周期

```
GraphExecutor.execute()
  │
  ├── Phase 1: LOAD
  │   └── 遍历所有节点调用 node.load()
  │       ├── FMULocal: 解压 FMU → 解析 modelDescription.xml → 建立 value_reference 映射
  │       ├── FMUStub:  建立 ZMQ REQ 连接 → 发送 LOAD 指令
  │       └── Operator: 无操作
  │
  ├── Phase 2: INIT
  │   ├── 遍历所有节点调用 node.init(start_time, stop_time)
  │   │   ├── FMULocal: instantiate() → setupExperiment() → enterInitializationMode()
  │   │   │             → exitInitializationMode() → pull_outputs()
  │   │   └── Operator: 绑定 compute_fn 到 OperatorOutput
  │   ├── 初始变量交换: 遍历所有 Arrow 执行 transfer()
  │   └── 代数环求解: CoInitializer.solve()
  │       ├── Tarjan SCC 检测
  │       └── Newton-Raphson 迭代求解（如有环）
  │
  ├── Phase 3: SIMULATE
  │   └── while current_time < stop_time:
  │       ├── Stepper 计算步长 dt
  │       ├── 保存状态（自适应步长模式下）
  │       ├── Iterator.iterate(current_time, dt)
  │       │   ├── 并行/串行: 所有节点 step(dt)
  │       │   ├── 屏障同步（并行模式下等待所有 future 完成）
  │       │   └── 顺序变量交换: 遍历所有 Arrow.transfer()
  │       ├── 失败处理: 回滚状态 → 缩小步长 → 重试
  │       ├── current_time += dt
  │       └── Exporter.record(current_time)
  │
  └── Phase 4: TERMINATE
      └── 遍历所有节点调用 node.terminate()
          ├── FMULocal: fmu.terminate() → fmu.freeInstance() → 清理解压目录
          └── FMUStub: 发送 TERMINATE 指令 → 关闭 ZMQ 连接
```

### 3.2 单步执行细节（Iterator.iterate）

```
Iterator.iterate(current_time, dt)
  │
  ├── Step 1: 执行节点步进
  │   ├── 串行模式: for node in nodes: node.step(current_time, dt)
  │   └── 并行模式: ThreadPoolExecutor.submit(node.step, ...) for each node
  │
  ├── Step 2: 屏障同步（并行模式）
  │   └── for future in as_completed(futures): future.result()
  │
  └── Step 3: 变量交换
      └── for arrow in arrows: arrow.transfer()
          # output.value → input.value (顺序执行，避免竞态)
```

---

## 4. 数据模型设计

### 4.1 节点类型继承体系

```
GraphNode (ABC)
│   属性: node_id, inputs: list[Input], outputs: list[Output]
│   抽象方法: load(), init(), step(), terminate()
│   可选方法: save_state(), restore_state(), pull_outputs(), push_inputs()
│
├── FMULocal (GraphNode, FMUProxy)
│   本地 FMU 执行节点，通过 fmpy 操作 FMU2Slave
│   属性: fmu_path, before_init_values, _model_description, _fmu, _vr_map
│   │
│   └── (FMUSoul 持有 FMULocal 实例，非继承关系)
│
├── FMUStub (GraphNode, FMUProxy)
│   分布式代理节点，通过 ZMQ REQ 转发指令
│   属性: address, _context: zmq.Context, _socket: zmq.Socket
│
├── Operator (GraphNode, ABC)
│   数学运算节点基类
│   抽象方法: _compute()
│   │
│   ├── Adder          # output = sum(inputs)
│   ├── Multiplier     # output = product(inputs)
│   ├── Gain           # output = input × gain
│   └── Offset         # output = input + offset
│
├── ExternalInput (GraphNode)
│   外部输入节点，仅有 outputs
│
└── ExternalOutput (GraphNode)
    外部输出节点，仅有 inputs
```

### 4.2 变量类型继承体系

```
Variable (dataclass)
│   属性: id: str, data_type: DataType, value: Any
│
├── Input (Variable)
│   └── FMUInput (Input)
│       额外属性: vr: int (FMI value reference)
│       方法: push(proxy, value) → 调用 proxy.push(vr, value, data_type)
│
└── Output (Variable)
    ├── FMUOutput (Output)
    │   额外属性: vr: int
    │   方法: pull(proxy) → 调用 proxy.pull(vr, data_type)
    │
    └── OperatorOutput (Output)
        额外属性: compute_fn: Callable
        方法: pull() → 调用 compute_fn() 惰性求值
```

### 4.3 数据类型枚举

```python
class DataType(Enum):
    REAL    = "Real"       # default: 0.0
    INTEGER = "Integer"    # default: 0
    BOOLEAN = "Boolean"    # default: False
    STRING  = "String"     # default: ""
```

### 4.4 连接与图

**Arrow（有向连接）：**

```python
@dataclass
class Arrow:
    from_output: Output    # 源输出端口
    to_input: Input        # 目标输入端口

    def transfer(self):
        self.to_input.value = self.from_output.value
```

**Graph（运行时仿真图）：**

```python
@dataclass
class Graph:
    settings: RuntimeSettings
    nodes: list[GraphNode]
    arrows: list[Arrow]
    export: ExportConfig
```

### 4.5 FMUProxy 抽象接口

```python
class FMUProxy(ABC):
    # --- 生命周期 ---
    def load(self, path: str) -> None
    def instantiate(self) -> None
    def init(self, start_time: float, stop_time: float) -> None
    def step(self, current_time: float, dt: float) -> bool
    def terminate(self) -> None

    # --- 变量读写 ---
    def push(self, vr: int, value: Any, data_type: DataType) -> None
    def pull(self, vr: int, data_type: DataType) -> Any

    # --- 状态管理（回滚用） ---
    def save_state(self) -> None
    def restore_state(self) -> None

    # --- 导数计算（代数环用，有默认实现） ---
    def derivative_of_io(self, input_vr, output_vr, delta=1e-6) -> float
        # 有限差分近似: (f(x+δ) - f(x)) / δ
    def derivative_of(self, output_vr: int) -> float
        # 时间导数（默认返回 0.0）
```

### 4.6 运行时配置数据类

```python
@dataclass
class RuntimeSettings:
    start_time: float = 0.0
    stop_time: float = 10.0
    co_initialization: CoInitSettings    # 代数环求解参数
    stepper: StepperSettings             # 步进策略参数
    zmq: ZMQSettings                     # 分布式通信参数

@dataclass
class CoInitSettings:
    residuals_tolerance: float = 1e-5    # 收敛容差
    max_iterations: int = 100            # 最大迭代次数

@dataclass
class StepperSettings:
    method: str = "constant"             # constant | euler | adams_bashforth
    step_size: float = 0.1              # 初始/固定步长
    min_step: float = 0.01              # 最小步长（自适应）
    max_step: float = 1.0               # 最大步长（自适应）
    safety_factor: float = 0.9          # 安全因子
    order: int = 3                       # Adams-Bashforth 阶数

@dataclass
class ZMQSettings:
    coordinator_address: str = "tcp://localhost:5555"

@dataclass
class ExportConfig:
    folder: str = "./output"             # 输出目录
    prefix: str = "results"              # 文件名前缀
    variables: list[str] = ["all"]       # 导出变量列表
```

---

## 5. 引擎层详细设计

### 5.1 步进器（Stepper）继承体系

```
Stepper (ABC)
│   属性: settings: StepperSettings, step_size: float
│   抽象方法:
│     next_step_size(current_time, errors=None) -> float
│     should_rollback(errors: list[float]) -> bool
│
├── ConstantStepper
│   固定步长，不自适应，不回滚
│   next_step_size() → 始终返回 settings.step_size
│   should_rollback() → 始终返回 False
│
├── EulerStepper
│   一阶误差估计，自适应步长
│   dt_new = safety × dt × (tol / error)
│   回滚条件: max_error > step_size × 10
│
└── AdamsBashforthStepper
    多步法，高阶误差估计
    dt_new = safety × dt × (tol / error)^(1/(order+1))
    维护 error_history 队列（长度 = order）
    回滚条件: max_error > step_size × 10
```

### 5.2 代数环求解器（CoInitializer）

**算法流程：**

```
CoInitializer.solve()
  │
  ├── 1. 构建邻接表
  │   遍历所有 Arrow，从 from_output 的宿主节点 → to_input 的宿主节点
  │
  ├── 2. Tarjan SCC 检测
  │   找出所有强连通分量（Strongly Connected Components）
  │   过滤出 |SCC| > 1 的环
  │
  └── 3. 对每个代数环执行 Newton-Raphson
      ├── 收集环内箭头
      ├── 迭代（最多 max_iterations 次）:
      │   ├── 计算残差: r_i = output_i.value - input_i.value
      │   ├── 收敛判定: max|r_i| < tolerance → 完成
      │   ├── 有限差分构建雅可比矩阵 J
      │   │   对每个输入 j 施加 δ 扰动 → 重新求值 → 计算 ∂r_i/∂x_j
      │   ├── 求解线性系统: J · Δx = r
      │   └── 修正: input_i.value -= Δx_i
      └── 超过最大迭代次数 → 抛出 CoInitError
```

### 5.3 并行计算模型（BSP）

```
BSP (Bulk Synchronous Processing) 模型:

  ┌──────────────────────────────────────────────┐
  │ Step 1: 并行执行                              │
  │                                              │
  │  ThreadPoolExecutor                          │
  │  ┌────────┐ ┌────────┐ ┌────────┐           │
  │  │ Node A │ │ Node B │ │ Node C │  ...       │
  │  │ step() │ │ step() │ │ step() │           │
  │  └────────┘ └────────┘ └────────┘           │
  ├──────────────────────────────────────────────┤
  │ Step 2: 屏障同步                              │
  │  as_completed(futures) → 等待所有节点完成       │
  ├──────────────────────────────────────────────┤
  │ Step 3: 顺序变量交换                           │
  │  for arrow in arrows:                        │
  │      arrow.transfer()  # 避免竞态条件          │
  └──────────────────────────────────────────────┘
```

### 5.4 数据导出器（Exporter）

- 根据 `ExportConfig.variables` 构建列头
  - `["all"]`：导出所有节点的所有输出变量
  - `["Node1.y", "Node2.u"]`：导出指定变量
- CSV 格式：`time, Node1.y, Node2.y, ...`
- 在 Phase 3 每个时间步调用 `record(time)`
- 输出路径：`{folder}/{prefix}.csv`

---

## 6. 分布式架构

### 6.1 Stub/Soul 代理模式

```
Coordinator (主节点)                    Worker (工作节点)
┌─────────────────┐                    ┌─────────────────┐
│  GraphExecutor   │                    │   FMUSoul        │
│  ┌────────────┐  │                    │  ┌────────────┐  │
│  │ FMULocal A │  │                    │  │ FMULocal C │  │
│  └────────────┘  │                    │  └────────────┘  │
│  ┌────────────┐  │     ZMQ REQ       │  ┌────────────┐  │
│  │ FMULocal B │  │ ─────────────────► │  │ ZMQ REP    │  │
│  └────────────┘  │ ◄───────────────── │  │ Server     │  │
│  ┌────────────┐  │     ZMQ REP       │  └────────────┘  │
│  │ FMUStub C  │──┘                    └─────────────────┘
│  │ (代理)     │
│  └────────────┘
└─────────────────┘
```

**FMUStub（主节点侧）：**
- 实现 `GraphNode` + `FMUProxy` 接口
- 持有 ZMQ REQ socket
- 所有方法（load/init/step/push/pull/save/restore）转换为 `Request` → 发送 → 接收 `Response`

**FMUSoul（工作节点侧）：**
- 持有 `FMULocal` 实例
- 持有 ZMQ REP socket
- `serve_forever()` 主循环：接收 `Request` → `_dispatch()` → 返回 `Response`

### 6.2 通信协议

```python
class Command(Enum):
    LOAD          = "load"
    INIT          = "init"
    STEP          = "step"
    GET           = "get"           # 读取变量
    SET           = "set"           # 设置变量
    SAVE_STATE    = "save_state"
    RESTORE_STATE = "restore_state"
    TERMINATE     = "terminate"
```

**消息格式（JSON over ZMQ）：**

Request:
```json
{
  "command": "step",
  "params": {
    "current_time": 0.5,
    "dt": 0.1
  }
}
```

Response:
```json
{
  "success": true,
  "data": true,
  "error": null
}
```

### 6.3 变量读写协议

GET 请求：
```json
{"command": "get", "params": {"vr": 1, "data_type": "Real"}}
```

SET 请求：
```json
{"command": "set", "params": {"vr": 1, "value": 3.14, "data_type": "Real"}}
```

---

## 7. 配置规范

### 7.1 JSON 配置 Schema

```json
{
  "settings": {
    "start_time": 0.0,
    "stop_time": 10.0,
    "co_initialization": {
      "residuals_tolerance": 1e-5,
      "max_iterations": 100
    },
    "stepper": {
      "method": "constant",
      "step_size": 0.1,
      "min_step": 0.01,
      "max_step": 1.0,
      "safety_factor": 0.9,
      "order": 3
    },
    "zmq": {
      "coordinator_address": "tcp://localhost:5555"
    }
  },
  "nodes": [ ... ],
  "arrows": [ ... ],
  "export": { ... }
}
```

### 7.2 节点类型配置

#### FMU 节点

```json
{
  "type": "fmu",
  "id": "Plant",
  "path": "./fmus/plant.fmu",
  "inputs": [
    {"id": "u", "type": "Real"}
  ],
  "outputs": [
    {"id": "y", "type": "Real"}
  ],
  "before_init_values": [
    {"name": "param1", "value": 1.0}
  ]
}
```

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `type` | string | 是 | 固定 `"fmu"` |
| `id` | string | 是 | 节点唯一标识符 |
| `path` | string | 是 | FMU 文件相对路径（相对于配置文件所在目录） |
| `inputs` | array | 否 | 输入变量列表 |
| `outputs` | array | 否 | 输出变量列表 |
| `before_init_values` | array | 否 | 初始化前设置的参数 |

#### Operator 节点

```json
{
  "type": "operator",
  "operator_type": "gain",
  "id": "Gain1",
  "value": 2.5,
  "inputs": [
    {"id": "input", "type": "Real"}
  ]
}
```

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `type` | string | 是 | 固定 `"operator"` |
| `operator_type` | string | 是 | `adder` / `multiplier` / `gain` / `offset` |
| `id` | string | 是 | 节点唯一标识符 |
| `value` | float | gain/offset 必填 | 增益系数或偏移量 |
| `inputs` | array | 否 | 输入变量列表 |

> Operator 的输出由引擎自动创建（id 固定为 `"output"`，类型为 `Real`）

#### ExternalInput / ExternalOutput 节点

```json
{"type": "external_input",  "id": "Signal",  "outputs": [{"id": "value", "type": "Real"}]}
{"type": "external_output", "id": "Monitor", "inputs":  [{"id": "value", "type": "Real"}]}
```

### 7.3 箭头配置

```json
{
  "arrows": [
    {"from": "Plant.y",      "to": "Controller.u"},
    {"from": "Controller.y", "to": "Plant.u"}
  ]
}
```

格式：`"NodeId.VarId"`，其中 `NodeId` 为节点 `id`，`VarId` 为变量 `id`。

### 7.4 导出配置

```json
{
  "export": {
    "folder": "./output",
    "prefix": "results",
    "variables": ["all"]
  }
}
```

| 字段 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `folder` | string | `"./output"` | 输出目录（自动创建） |
| `prefix` | string | `"results"` | 文件名前缀，生成 `{prefix}.csv` |
| `variables` | array | `["all"]` | `["all"]` 导出全部输出变量，或指定 `["Node.var"]` |

### 7.5 变量类型

变量 `type` 字段支持以下值：

| 值 | Python 类型 | 默认值 |
|----|------------|--------|
| `"Real"` | float | 0.0 |
| `"Integer"` | int | 0 |
| `"Boolean"` | bool | False |
| `"String"` | str | "" |

### 7.6 步进器方法

| 方法 | 说明 | 关键参数 |
|------|------|---------|
| `constant` | 固定步长 | `step_size` |
| `euler` | 一阶自适应 | `step_size`, `min_step`, `max_step`, `safety_factor` |
| `adams_bashforth` | 多步法自适应 | `step_size`, `min_step`, `max_step`, `safety_factor`, `order` |

---

## 8. CLI 接口

### 8.1 命令总览

```bash
pycosim <command> [options]
```

| 命令 | 说明 |
|------|------|
| `simulate` | 运行仿真任务 |
| `worker` | 启动分布式工作节点 |

### 8.2 simulate 命令

```bash
pycosim simulate <config> [--parallel] [--workers N] [-v|-vv]
```

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `config` | 位置参数 | 是 | JSON 配置文件路径 |
| `--parallel` | 标志 | 否 | 启用多核并行执行 |
| `--workers` | 整数 | 否 | 最大并行工作线程数 |
| `-v` | 标志 | 否 | 日志级别 INFO |
| `-vv` | 标志 | 否 | 日志级别 DEBUG |

### 8.3 worker 命令

```bash
pycosim worker --fmu <path> --node-id <id> [--address <addr>] [-v]
```

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `--fmu` | 字符串 | 是 | FMU 文件路径 |
| `--node-id` | 字符串 | 是 | 节点标识符 |
| `--address` | 字符串 | 否 | ZMQ 绑定地址（默认 `tcp://localhost:5555`） |
| `-v` | 标志 | 否 | 增加日志详细程度 |

### 8.4 也可通过 python -m 调用

```bash
python -m pycosim simulate config.json --parallel -vv
```

---

## 9. 关键设计决策

| 决策项 | 选择 | 理由 |
|--------|------|------|
| FMU 运行库 | fmpy | Python 生态最成熟的 FMI 库，支持 FMI 1.0/2.0/3.0 |
| 分布式通信 | ZeroMQ (REQ/REP) | 轻量无中间件，替代 DACCOSIM 的 JMS/ActiveMQ |
| 并行计算 | concurrent.futures.ThreadPoolExecutor | Python 标准库，BSP 模式天然适配 |
| 线性代数 | numpy | 替代 DACCOSIM 的 JAMA 矩阵库，用于雅可比求解 |
| 配置格式 | JSON | 与 DACCOSIM 一致，简洁可读 |
| SCC 检测 | Tarjan 算法 | O(V+E) 复杂度，经典可靠 |
| 代数环求解 | Newton-Raphson + 有限差分雅可比 | 通用且不依赖 FMU 提供解析导数 |
| 代理模式 | Stub/Soul | 对 GraphExecutor 透明，本地与分布式统一接口 |
| 变量交换 | 顺序执行 | 避免并行模式下的竞态条件 |
| 状态管理 | FMI getFMUstate/setFMUstate | 标准 FMI 2.0 接口，支持自适应回滚 |

---

## 10. 项目结构

```
pycosim/
├── pyproject.toml                          # 构建配置与依赖声明
├── environment.yml                         # Conda 环境定义（包管理入口）
├── src/pycosim/
│   ├── __init__.py                         # 包入口，版本号
│   ├── __main__.py                         # python -m pycosim 入口
│   ├── cli.py                              # CLI 命令行解析与分发
│   ├── exceptions.py                       # 异常层次结构
│   ├── data_type.py                        # DataType 枚举 (Real/Integer/Boolean/String)
│   │
│   ├── config/                             # ── 配置层 ──
│   │   ├── __init__.py
│   │   └── loader.py                       # JSON → Graph 解析器
│   │
│   ├── model/                              # ── 模型层 ──
│   │   ├── __init__.py
│   │   ├── variable.py                     # Variable/Input/Output/FMUInput/FMUOutput/OperatorOutput
│   │   ├── arrow.py                        # Arrow (有向连接)
│   │   ├── graph_node.py                   # GraphNode ABC
│   │   ├── fmu_proxy.py                    # FMUProxy ABC
│   │   ├── graph.py                        # Graph (运行时仿真图)
│   │   ├── settings.py                     # RuntimeSettings 及子配置
│   │   ├── inputs/
│   │   │   └── __init__.py
│   │   ├── outputs/
│   │   │   └── __init__.py
│   │   └── nodes/
│   │       ├── __init__.py
│   │       ├── fmu_local.py                # FMULocal (本地 FMU 执行)
│   │       ├── fmu_stub.py                 # FMUStub (ZMQ REQ 代理)
│   │       ├── fmu_soul.py                 # FMUSoul (ZMQ REP 工作端)
│   │       ├── external_input.py           # ExternalInput
│   │       ├── external_output.py          # ExternalOutput
│   │       └── operators/
│   │           ├── __init__.py
│   │           ├── base.py                 # Operator ABC
│   │           ├── adder.py                # Adder (加法器)
│   │           ├── multiplier.py           # Multiplier (乘法器)
│   │           ├── gain.py                 # Gain (增益)
│   │           └── offset.py               # Offset (偏移)
│   │
│   ├── engine/                             # ── 执行层 ──
│   │   ├── __init__.py
│   │   ├── graph_executor.py               # GraphExecutor (4阶段生命周期)
│   │   ├── iterator.py                     # Iterator (BSP 步进+交换)
│   │   ├── co_initializer.py               # CoInitializer (代数环求解)
│   │   ├── exporter.py                     # Exporter (CSV 导出)
│   │   └── steppers/
│   │       ├── __init__.py
│   │       ├── base.py                     # Stepper ABC
│   │       ├── constant.py                 # ConstantStepper
│   │       ├── euler.py                    # EulerStepper
│   │       └── adams_bashforth.py          # AdamsBashforthStepper
│   │
│   └── distributed/                        # ── 分布式层 ──
│       ├── __init__.py
│       ├── protocol.py                     # Command/Request/Response (ZMQ 消息协议)
│       └── worker.py                       # Worker (独立工作进程)
│
├── tests/                                  # 测试
│   ├── conftest.py                         # MockFMUProxy, MockFMUNode
│   ├── test_data_type.py
│   ├── test_variable.py
│   ├── test_arrow.py
│   ├── test_operators.py
│   ├── test_graph_node.py
│   ├── test_iterator.py
│   ├── test_stepper.py
│   ├── test_exporter.py
│   ├── test_co_initializer.py
│   ├── test_graph_executor.py
│   ├── test_config_loader.py
│   └── test_protocol.py
│
└── examples/
    ├── simple_two_fmu.json                 # 双 FMU 闭环仿真示例
    └── operators_only.json                 # 纯 Operator 链路示例
```

---

## 11. 依赖与环境

项目使用 **Conda** 进行包管理与环境隔离，环境定义文件为 `environment.yml`。

### 11.1 environment.yml

```yaml
name: pycosim
channels:
  - conda-forge
  - defaults
dependencies:
  - python>=3.10
  - numpy>=1.24            # 线性代数（雅可比矩阵求解）
  - pyzmq>=25.0            # ZeroMQ 分布式通信
  - pytest>=7.0            # 测试框架
  - pip
  - pip:
    - fmpy>=0.3.28          # FMU 解压/加载/执行（仅 PyPI 分发）
```

> `fmpy` 未在 conda-forge 上发布，因此通过 `pip` 子依赖安装。其余包优先从 conda-forge 通道获取。

### 11.2 依赖说明

| 包 | 通道 | 用途 |
|----|------|------|
| `numpy>=1.24` | conda-forge | 线性代数运算（代数环雅可比矩阵求解） |
| `pyzmq>=25.0` | conda-forge | ZeroMQ 分布式通信（Stub/Soul 协议） |
| `pytest>=7.0` | conda-forge | 单元/集成测试框架 |
| `fmpy>=0.3.0` | pip (PyPI) | FMU 解压、模型描述解析、FMI 2.0 Slave 执行 |

### 11.3 pyproject.toml（构建配置）

`pyproject.toml` 保留用于定义项目元数据、入口脚本和 `pip install -e .` 的可编辑安装：

```toml
[project]
name = "pycosim"
version = "0.1.0"
requires-python = ">=3.10"
dependencies = ["fmpy>=0.3.0", "numpy>=1.24", "pyzmq>=25.0"]

[project.optional-dependencies]
dev = ["pytest>=7.0"]

[project.scripts]
pycosim = "pycosim.cli:main"
```

### 11.4 环境安装与管理

```bash
# 从零创建环境
conda env create -f environment.yml

# 激活环境
conda activate pycosim

# 以可编辑模式注册项目（提供 pycosim CLI 入口）
pip install -e .

# 更新已有环境（依赖变更后）
conda env update -f environment.yml --prune

# 导出当前环境精确版本（用于复现）
conda env export > environment.lock.yml

# 删除环境
conda env remove -n pycosim
```

### 11.5 验证安装

```bash
# 确认 CLI 可用
pycosim --help

# 确认依赖完整
python -c "import fmpy, numpy, zmq; print('All dependencies OK')"

# 运行测试
pytest tests/ -v
```

---

## 12. 测试策略

### 12.1 测试层次

| 层次 | 策略 | 工具 |
|------|------|------|
| 单元测试 | 每个模块独立测试 | `MockFMUProxy` / `MockFMUNode` |
| 集成测试 | 多节点联合仿真 | `GraphExecutor` + `MockFMUNode` |
| 分布式测试 | 进程内 ZMQ 通信 | `Protocol` 编解码测试 |

### 12.2 Mock 对象

**MockFMUProxy：**
- 实现 `FMUProxy` 全部接口
- 简单动力学：`output[vr+100] = input[vr] * 2.0`
- 支持 `save_state()` / `restore_state()`

**MockFMUNode：**
- 包装 `MockFMUProxy` 的 `GraphNode` 实现
- 完整实现 4 阶段生命周期
- 支持 `FMUInput` / `FMUOutput` 读写委托

### 12.3 测试清单（31 项）

| 测试文件 | 测试数 | 覆盖范围 |
|----------|--------|---------|
| `test_data_type.py` | 3 | DataType 枚举值、默认值、字符串转换 |
| `test_variable.py` | 5 | Variable 初始化、FMUInput.push、FMUOutput.pull、OperatorOutput |
| `test_arrow.py` | 2 | Arrow.transfer（Real 和 String 类型） |
| `test_operators.py` | 4 | Adder / Multiplier / Gain / Offset |
| `test_graph_node.py` | 3 | MockFMUNode 生命周期、get_input/get_output、状态保存恢复 |
| `test_iterator.py` | 2 | 串行迭代、并行迭代 |
| `test_stepper.py` | 3 | ConstantStepper / EulerStepper / AdamsBashforthStepper |
| `test_exporter.py` | 1 | CSV 文件生成与内容验证 |
| `test_co_initializer.py` | 2 | 无环检测、SCC 检测 |
| `test_graph_executor.py` | 1 | 完整 4 阶段仿真生命周期 |
| `test_config_loader.py` | 2 | Operator 配置加载、缺失文件错误 |
| `test_protocol.py` | 3 | Request/Response 编解码、错误响应 |

### 12.4 运行测试

```bash
# 全部测试
pytest tests/ -v

# 单个模块
pytest tests/test_operators.py -v

# 带覆盖率
pytest tests/ --cov=pycosim --cov-report=term-missing
```

---

## 13. 使用示例

### 13.1 本地固定步长仿真

```bash
pycosim simulate examples/simple_two_fmu.json -v
```

配置文件 `simple_two_fmu.json`：

```json
{
  "settings": {
    "start_time": 0.0,
    "stop_time": 10.0,
    "stepper": {"method": "constant", "step_size": 0.1}
  },
  "nodes": [
    {
      "type": "fmu", "id": "Plant",
      "path": "./fmus/plant.fmu",
      "inputs":  [{"id": "u", "type": "Real"}],
      "outputs": [{"id": "y", "type": "Real"}]
    },
    {
      "type": "fmu", "id": "Controller",
      "path": "./fmus/controller.fmu",
      "inputs":  [{"id": "u", "type": "Real"}],
      "outputs": [{"id": "y", "type": "Real"}]
    }
  ],
  "arrows": [
    {"from": "Plant.y",      "to": "Controller.u"},
    {"from": "Controller.y", "to": "Plant.u"}
  ],
  "export": {"folder": "./output", "prefix": "results", "variables": ["all"]}
}
```

### 13.2 并行自适应步长仿真

```bash
pycosim simulate config.json --parallel --workers 4 -vv
```

配置中使用 Euler 自适应步进器：

```json
{
  "settings": {
    "stepper": {
      "method": "euler",
      "step_size": 0.1,
      "min_step": 0.001,
      "max_step": 0.5,
      "safety_factor": 0.9
    }
  }
}
```

### 13.3 分布式仿真

**工作节点（先启动）：**

```bash
pycosim worker --fmu ./fmus/plant.fmu --node-id Plant \
               --address tcp://0.0.0.0:5555 -v
```

**主节点（后启动）：**

在配置文件中将对应节点声明为远程节点（当前版本需代码方式组装 FMUStub），或未来扩展 JSON 配置支持 `"type": "fmu_remote"` 类型。

### 13.4 纯 Operator 链路测试

```bash
pycosim simulate examples/operators_only.json -v
```

```json
{
  "nodes": [
    {"type": "external_input", "id": "Signal", "outputs": [{"id": "value", "type": "Real"}]},
    {"type": "operator", "operator_type": "gain", "id": "Gain1", "value": 2.5,
     "inputs": [{"id": "input", "type": "Real"}]},
    {"type": "operator", "operator_type": "offset", "id": "Offset1", "value": 10.0,
     "inputs": [{"id": "input", "type": "Real"}]}
  ],
  "arrows": [
    {"from": "Signal.value", "to": "Gain1.input"},
    {"from": "Gain1.output", "to": "Offset1.input"}
  ]
}
```

### 13.5 程序化使用（Python API）

```python
from pycosim.config.loader import load_graph
from pycosim.engine.graph_executor import GraphExecutor

# 从配置加载
graph = load_graph("config.json")

# 执行仿真
executor = GraphExecutor(graph, parallel=True, max_workers=4)
executor.execute()

# 结果在 export.folder/export.prefix.csv
```

---

## 附录：异常层次

```
PyCosimError (基类)
├── ConfigError          # 配置解析错误（JSON 格式、缺失字段、未知节点类型）
├── SimulationError      # 仿真执行错误
│   └── StepError        # 步进失败（发散、NaN）
├── FMUError             # FMU 操作错误（加载/实例化/步进）
├── CoInitError          # 代数环求解失败（不收敛、奇异雅可比）
└── DistributedError     # 分布式通信错误（ZMQ 连接/远程异常）
```

---

## 附录：模块依赖拓扑

```
exceptions.py  ←─────────────────────────────────────────┐
data_type.py   ←────────────┐                            │
                             │                            │
model/variable.py ←──── data_type                        │
model/arrow.py ←──── variable                            │
model/graph_node.py ←── variable                         │
model/fmu_proxy.py ←── data_type                         │
model/settings.py  (独立)                                 │
model/graph.py ←── arrow, graph_node, settings            │
                                                          │
model/nodes/fmu_local.py ←── graph_node, fmu_proxy,      │
                              variable, data_type ────► exceptions
model/nodes/fmu_stub.py ←── graph_node, fmu_proxy,       │
                              protocol ───────────────► exceptions
model/nodes/fmu_soul.py ←── fmu_local, protocol           │
model/nodes/operators/* ←── graph_node, variable           │
                                                          │
config/loader.py ←── model/* ─────────────────────────► exceptions
                                                          │
engine/steppers/* ←── settings                             │
engine/iterator.py ←── graph_node, arrow                   │
engine/co_initializer.py ←── graph, arrow, numpy ──────► exceptions
engine/exporter.py ←── graph                               │
engine/graph_executor.py ←── engine/*, graph ──────────► exceptions
                                                          │
distributed/protocol.py  (独立)                            │
distributed/worker.py ←── fmu_local, fmu_soul              │
                                                          │
cli.py ←── config/loader, engine/graph_executor,           │
            distributed/worker                             │
```
