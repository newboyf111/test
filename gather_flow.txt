# Gather 查找流程图

```mermaid
flowchart TD
    Start([开始查找 gather]) --> CheckTimeout{3秒内?}
    
    CheckTimeout -->|是| TryFind[尝试查找并点击 gather]
    CheckTimeout -->|否| Timeout[超时，未找到 gather]
    
    TryFind --> ClickGather[点击 gather]
    ClickGather --> FindSuccess{查找成功?}
    
    FindSuccess -->|是| ClickSuccess[点击 gather 成功]
    ClickSuccess --> CheckGatherExist{gather 仍然存在?}
    
    CheckGatherExist -->|是| ClickFailed[点击失败，停止挖矿]
    ClickFailed --> StopMining[设置 is_mining=False, mined=True]
    StopMining --> NotifyStop[通知挖矿停止]
    NotifyStop --> End([结束])
    
    CheckGatherExist -->|否| CheckTeam{找到 team?}
    CheckTeam -->|是| QueueFull[队列已满，停止挖矿]
    QueueFull --> StopMining2[设置 is_mining=False, mined=True]
    StopMining2 --> NotifyStop2[通知挖矿停止]
    NotifyStop2 --> End2([结束])
    
    CheckTeam -->|否| ContinueMining[继续挖矿流程]
    ContinueMining --> End3([结束])
    
    FindSuccess -->|否| FindFailed[未找到 gather]
    FindFailed --> ExecuteFallback[执行备选方案]
    
    ExecuteFallback --> Sleep1[等待 1-2 秒]
    Sleep1 --> GetWindowSize[获取窗口尺寸]
    GetWindowSize --> CalcDrag[计算拖动距离]
    CalcDrag --> DragLeft[向左拖动]
    DragLeft --> Sleep2[等待 1-2 秒]
    Sleep2 --> ClickSearch[点击 search_meat]
    ClickSearch --> ClickSearchSuccess{点击成功?}
    
    ClickSearchSuccess -->|是| Sleep3[等待 1-2 秒]
    Sleep3 --> RetryFind[重新查找 gather]
    RetryFind --> CheckTimeout
    
    ClickSearchSuccess -->|否| LogWarning[记录警告日志]
    LogWarning --> RetryFind
    
    Timeout --> SetResourceIndex[更新资源索引]
    SetResourceIndex --> Return([返回])
```

# 流程说明

## 主要逻辑
1. **3秒超时机制**：在3秒内不断尝试查找并点击 gather
2. **查找成功**：点击 gather，然后检查 gather 是否仍然存在
3. **点击失败**：如果 gather 仍然存在，说明点击失败，停止挖矿
4. **查找失败**：执行备选方案（向左移动并重新点击 search_meat）
5. **备选方案**：
   - 等待 1-2 秒
   - 获取窗口尺寸，计算拖动距离
   - 向左拖动
   - 等待 1-2 秒
   - 点击 search_meat
   - 重新查找 gather
6. **超时处理**：3秒内未找到 gather，更新资源索引并返回

## 关键判断点
- **gather 仍然存在**：说明点击失败，停止挖矿
- **找到 team**：说明队列已满，停止挖矿
- **点击成功**：继续挖矿流程

## 次要逻辑
- 用户手动停止：随时检查 `_user_stopped` 标志
- 窗口尺寸自适应：根据窗口宽度计算拖动距离（基准30像素）
