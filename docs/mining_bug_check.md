# mining.py Bug 检查报告（新版本）

> **审查文件**: `mining.py` (1681 行)
> **审查日期**: 2026-04-13
> **对比基准**: 之前版本的 `project_review.md` 和 `flowchart_review.md`

---

## 一、严重 Bug（4 个）

### BUG-1: `stop_mining()` → `_try_start_next_window()` 死锁 [严重]

**位置**: L1272 + L1286 + L1391

**问题描述**:

```python
# L1272: stop_mining() 获取 _lock
def stop_mining(self, hwnd: int, user_stopped: bool = False) -> bool:
    with self._lock:                          # ← 获取 _lock
        ...
        if was_mining and not user_stopped:
            self._try_start_next_window()      # L1286: 调用

# L1382-1391: _try_start_next_window() 再次获取 _lock
def _try_start_next_window(self):
    with self._scheduler_lock:                # 先获取 scheduler_lock
        ...
    with self._lock:                          # L1391: ← 再次获取 _lock → 死锁！
```

`_lock` 是 `threading.Lock()`（L1192），**不可重入**。`stop_mining()` 持有 `_lock` 时调用 `_try_start_next_window()`，后者再次尝试获取 `_lock`，导致**永久死锁**。

**触发条件**: 任何一个窗口挖矿自然结束（非用户手动停止）时触发。

**影响**: 整个挖矿管理器冻结，所有后续窗口无法启动。

**修复方案**:

```python
# 方案1: 在调用前释放锁
def stop_mining(self, hwnd: int, user_stopped: bool = False) -> bool:
    should_try_next = False
    with self._lock:
        ...
        if was_mining and not user_stopped:
            should_try_next = True
    if should_try_next:
        self._try_start_next_window()  # 在锁外调用
    return True

# 方案2: 将 _lock 改为 RLock（不推荐，掩盖设计问题）
self._lock = threading.RLock()
```

---

### BUG-2: `is_mining` 在 OCR 检查失败时未重置 [高]

**位置**: L305 vs L322-328

**问题描述**:

```python
# L305: 设置为挖矿中
self.is_mining = True

# L322-328: OCR 失败路径
if not self._check_ocr_before_mining():
    self.mined = True
    self._set_mining_state(2)
    if self.mining_manager is not None:
        self.mining_manager._on_window_mining_stopped(self.hwnd)
    return False  # ← is_mining 仍为 True！
```

**影响**: 窗口状态卡死，`is_mining=True` 但实际未在挖矿。后续轮换会跳过此窗口。

**修复**: 在 L323 后添加 `self.is_mining = False`。

---

### BUG-3: `_click_and_align` 中 dx/dy 双重缩放 [高]

**位置**: L1103-1132

**问题描述**:

```python
# L1111: target_x 已缩放
target_x = int(target_x_base * scale)

# L1103: current_x 来自 _click_with_pos() → matcher.get_center()
# 返回的是相对于截图的坐标（截图 = 屏幕像素）
current_x = pos[0]  # 已经是屏幕像素

# L1125: dx 是两个屏幕像素的差值
dx = target_x - current_x  # 已经是屏幕像素差值

# L1131: 又乘以 scale ← 双重缩放！
dx_scaled = int(dx * scale)
```

**举例**: 窗口 1116px, scale=2.0, 需移动 78px → 实际移动 156px。

**修复**: `dx_scaled = dx`（直接使用，不再乘以 scale）。

---

### BUG-4: `max_cycles` 被 OCR 无条件覆盖 [高]

**位置**: L688

**问题描述**:

```python
self.max_cycles = remaining  # 每 30 秒无条件覆盖
```

如果 OCR 误识别或游戏计数器重置，`remaining` 可能变大，导致 `max_cycles` 被重置，挖矿永不停止。

**修复**: `self.max_cycles = min(self.max_cycles, remaining)`（只允许减少）。

---

## 二、中等 Bug（3 个）

### BUG-5: `town_found` 预扫描结果未复用 [中]

**位置**: L693-694 vs L763

```python
# L693-694: 预扫描
town_found = self._find("town")
wild_found = self._find("wild")

# L763: 丢弃预扫描结果，重新查找
if self._find("town"):  # ← 应使用 town_found
```

**影响**: 多余的截图+匹配操作，且两次结果可能因缓存过期而不一致。

---

### BUG-6: `_current_active_hwnd` 无锁访问 [中]

**位置**: L1194, L1241, L1250

```python
# L1241-1250: 无锁读写
def _ensure_window_active(self, hwnd, window_name):
    if self._current_active_hwnd != hwnd:  # 读
        ...
        self._current_active_hwnd = hwnd    # 写
```

多线程并发调用时可能出现竞态条件。

---

### BUG-7: `_user_stopped` 无线程安全保护 [中]

**位置**: L111, L397, L477

`_user_stopped` 是普通 `bool`，在主线程（`stop_mining`）和挖矿线程（`_mining_loop`）之间共享，没有使用 `threading.Event` 或锁保护。

---

## 三、低级 Bug（3 个）

### BUG-8: 注释与代码不一致

**位置**: L856 vs L858

```python
# L856: 注释说"最多8次"
# 尝试最多8次寻找并点击 gather

# L858: 实际只循环 7 次
max_attempts = 7
for attempt in range(max_attempts):  # 0-6，共 7 次
```

---

### BUG-9: 变量命名误导

**位置**: L1076-1077

```python
client_x = center[0]  # 实际是截图内坐标，不是客户区坐标
client_y = center[1]
screen_x = left + client_x  # left 来自 GetWindowRect（外框），不是客户区
screen_y = top + client_y
```

变量名 `client_x/client_y` 暗示客户区坐标，但实际是截图内坐标。由于截图也使用 `GetWindowRect`（外框），所以计算结果正确，但命名容易误导维护者。

---

### BUG-10: `_get_window_size()` 使用 `GetWindowRect` 返回外框尺寸

**位置**: L226-227

```python
left, top, right, bottom = win32gui.GetWindowRect(self.hwnd)
return (right - left, bottom - top)  # 外框尺寸（含标题栏）
```

如果用于计算缩放比例（如 L1110: `scale = win_w / 558`），而 `558` 是客户区宽度，则缩放比例会有偏差（偏差量 = 标题栏宽度 / 558）。

---

## 四、与之前版本对比

| Bug | 之前版本 | 新版本 | 状态 |
|-----|----------|--------|------|
| is_mining 未重置 | ❌ 存在 | ❌ **仍存在** | 未修复 |
| dx/dy 双重缩放 | ❌ 存在 | ❌ **仍存在** | 未修复 |
| max_cycles 无限重置 | ❌ 存在 | ❌ **仍存在** | 未修复 |
| town_found 未复用 | ❌ 存在 | ❌ **仍存在** | 未修复 |
| _current_active_hwnd 无锁 | ❌ 存在 | ❌ **仍存在** | 未修复 |
| 不可达代码 `if miner is None` | ❌ 存在 | ✅ **已删除** | 已修复 |
| back1 冗余搜索 | ❌ 存在 | ❌ **仍存在** | 未修复 |
| OCR 解析逻辑重复 | ❌ 存在 | ❌ **仍存在** | 未修复 |
| **stop_mining 死锁** | — | ❌ **新增** | **新 Bug** |
| 初始化失败计数器 | — | ✅ **已添加** | 新增功能 |
| 恢复失败计数器 | — | ✅ **已添加** | 新增功能 |
| 资源失败计数器 | — | ✅ **已添加** | 新增功能 |
| _state_lock 状态锁 | — | ✅ **已添加** | 改善 |
| battle 失败重试逻辑 | 简化 | ✅ **已完善** | 改善 |
| 倒计时检查 is_mining | 缺失 | ✅ **已添加** (L466) | 已修复 |

---

## 五、修复优先级

### 立即修复（会导致死锁或功能失效）

| Bug | 修复难度 | 改动量 |
|-----|----------|--------|
| **BUG-1 死锁** | 低 | 调整 3 行 |
| **BUG-2 is_mining 未重置** | 极低 | +1 行 |
| **BUG-3 双重缩放** | 低 | 改 2 行 |
| **BUG-4 max_cycles 覆盖** | 低 | 改 1 行 |

### 短期修复

| Bug | 修复难度 |
|-----|----------|
| BUG-5 town_found 复用 | 低 |
| BUG-6 添加窗口激活锁 | 低 |
| BUG-8 注释修正 | 极低 |
