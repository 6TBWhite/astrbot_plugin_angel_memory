## 最终自检

- JSON 合法（字符串内部无未转义英文双引号，引用用「」）
- `create` 无 `source_memory_ids`；`merge`/`updata` 有 source + memory
- `updata` 只有 1 个 source
- 相似优先 `merge`，冲突优先 `updata`
- 画像为空的群友至少提炼了一条画像

现在开始分析对话，仅输出 JSON。