## 动作语义

- **`create`**：新增记忆。不允许携带 `source_memory_ids`。
- **`merge`**：合并相似/重复/过时记忆。必须包含 `source_memory_ids`（可多条）+ `memory`。本质：删旧增新。
- **`updata`**：修正与事实冲突的旧记忆。结构与 merge 相同，但 `source_memory_ids` 只能 1 条。本质：删 1 增 1。

> 发现重复/过时/需收敛 → `merge`；发现事实冲突/需纠正 → `updata`。
> 不能把本该更新的内容写成两个 `create`。