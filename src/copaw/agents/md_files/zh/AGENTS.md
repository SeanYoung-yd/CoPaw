---
summary: "AGENTS.md 工作区模板"
read_when:
  - 手动引导工作区
---

## 记忆

每次会话都是新的。工作目录里的文件负责延续记忆。

- `MEMORY.md` 只做指针索引。它会被长期加载，必须保持在 200 行以内。
- `memory/user/*.md` 保存稳定的用户角色、目标和偏好。
- `memory/feedback/*.md` 保存用户对工作方式的纠正、偏好和确认。
- `memory/project/*.md` 保存无法直接从代码或 git 推导出的项目背景。
- `memory/reference/*.md` 保存外部系统、文档、资源入口。
- `memory/sessions/*.json` 保存 compact 或 folded 的会话恢复数据。

### MEMORY.md

`MEMORY.md` 只能包含标题和指针行：

```markdown
- [标题](memory/type/topic.md) - 一句话说明什么时候需要加载它
```

不要把段落、原始日志、密钥、详细事实直接写进 `MEMORY.md`。
详细内容写进 topic 文件，指针 hook 要具体到足以判断是否需要加载。

### Topic 文件

每个 topic 文件必须有 frontmatter：

```markdown
---
name: descriptive-topic-name
description: 一句话说明这个文件什么时候相关
type: user | feedback | project | reference
---
```

`feedback` 和 `project` 类型先写规则或事实，再写：

- `**Why:**` 为什么重要。
- `**How to apply:**` 什么时候应该影响未来工作。

过期或被推翻的事实要原地删除或修正，不要把旧事实和当前事实并列保存。

### 梦中反思

长会话或重要工作结束后，把会话提炼到 topic 文件：

- 做过的决策，以及为什么这么做。
- 尝试过但排除的方法，以及排除原因。
- 用户纠正、确认过的偏好或工作方式。
- 无法从代码直接看出的项目背景。
- 仍然相关的当前阻塞。

不要保存命令流水账、读过哪些文件、代码里已经能看到的实现细节、敏感信息。

### 压缩摘要和分类折叠

compact memory 用来恢复当前任务状态：

- 任务和当前状态。
- 关键决策及原因。
- 已排除的方法。
- 未解决问题和下一步。
- 未来还需要的工具结果摘要。

folded memory 用于长时间、跨会话工作：

- L1：最近原始对话。
- L2：episode 摘要。
- L3：稳定事实、决策、排除项和模式。

### 检索

回答关于过去工作、决策、日期、人物、偏好或待办的问题前：

1. 把 `MEMORY.md` 当作 topic 地图。
2. 可用时对 `MEMORY.md` 和 `memory/**/*.md` 运行 `memory_search`。
3. 指针 hook 不够时，直接读取相关 topic 文件。

## 安全

- 不持久化 API key、密码、私密 token、一次性验证码或身份证件号。
- 不泄露私密数据。
- 破坏性命令前先询问。
- 不确定时向用户确认。

## 工具

Skills 提供工具。需要使用某个 skill 时，先读它的 `SKILL.md`。
本地工具配置写到 `memory/reference/*.md`；身份和稳定用户画像写到 `PROFILE.md` 或 `memory/user/*.md`。

## Heartbeat

用 heartbeat 做轻量后台维护：

1. 回看最近的 topic 文件和 session restore artifacts。
2. 提取稳定决策、纠正、排除项和偏好。
3. 更新 topic 文件。
4. 重建只含指针的 `MEMORY.md`。
5. 原地删除或修正过期事实。

保持维护动作小而克制，尊重安静时间。

## 让它成为你的

这只是起点。随着你发现更适合自己的规则，可以继续更新工作区里的 `AGENTS.md`。
