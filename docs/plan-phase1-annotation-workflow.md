# Phase 1：标注修正工作流优化

> 状态：进行中 | 影响：后端 API ×4、前端页面/组件 ×6、新增 composables ×4、新增 store ×1

## 目标

从"检测错误 → 逐条手动修改"升级为"检测 → 审核 → 区域智能修正 / 批量修正 / 撤销保障"。
核心 UX 一句话：**跑完检测不满意，几秒就能修正回来**。

---

## 1. 检测预览与审核模式

### 1.1 问题
当前 `POST /api/v1/files/{id}/detect` 检测结果直接覆盖旧 auto 标注并写入数据库，用户无法预览和选择性地接受/拒绝。

### 1.2 后端变更

#### 新增 `POST /api/v1/files/{file_id}/detect/preview`
- Query: `algorithm`, `s1_only`
- 行为: 读取 WAV → 降采样 → 运行检测 → **不写 DB** → 返回标注列表
- 响应: `{ file_id, file_type, algorithm_used, detected_count, items: [...] }`

#### 新增 `POST /api/v1/annotations/accept`
- Body: `{ file_id: str, items: [{ annotation_type, start_time, end_time, confidence, label }] }`
- 行为: 事务 → 删除 file 旧 auto 标注 → 插入 items → 提交
- 响应: `{ accepted_count: int }`

### 1.3 前端变更

| 文件 | 改动 |
|------|------|
| `FileViewerView.vue` | 检测两步：preview → 审核面板 → accept 提交 |
| `stores/annotationReviewStore.ts` | 待审核队列、筛选、选中状态 |

#### 审核面板 UI
- DetectionPanel 下方展开（动画过渡）
- **波形叠加**: 新标注半透明绿色，旧 auto 标注浅粉色
- **标注列表**: 类型/时间/置信度(颜色条)/Accept/Reject 按钮
- **筛选**: 按类型 + 「仅低置信度(<0.6)」开关
- **批量**: 「全部接受」「全部拒绝」「按筛选接受」
- Apply → accept API → toast → 收起

---

## 2. 区域选择 + 智能重检测

### 2.1 问题
只能全量重跑，无法针对错误区域局部修正。

### 2.2 后端变更

#### 新增 `POST /api/v1/files/{file_id}/detect/region`
- Query: `start_time`, `end_time`, `algorithm`, `s1_only`
- 行为: 裁剪 WAV → 区域检测 → 时间映射回原始时间线
- 响应: `{ file_id, region, algorithm_used, detected_count, items: [...] }`

### 2.3 前端变更

| 文件 | 改动 |
|------|------|
| `composables/useRegionSelection.ts` | 套索选择状态 + canvas overlay 渲染 |
| `components/ui/ContextMenu.vue` | 通用右键菜单组件 |
| `FileViewerView.vue` | 集成区域选择 + 右键菜单 |

#### 交互
- 波形上 mousedown-drag → 蓝色半透明矩形区域
- 右键菜单: 「重新检测」「清除标注」「放大到此」「AI 分析(占位)」
- 区域重检结果以审核模式展示

---

## 3. 批量标注操作

### 3.1 问题
只能逐条编辑/删除。选 20 条错误标注需点 20 次删除。

### 3.2 后端变更

#### 新增 `PATCH /api/v1/annotations/batch`
- Body(更新): `{ ids: [str], updates: { annotation_type?, label?, confidence? } }`
- Body(删除): `{ ids: [str], action: "delete" }`

### 3.3 前端变更

| 文件 | 改动 |
|------|------|
| `composables/useAnnotationSelection.ts` | 多选状态、Shift/Cmd 选择 |
| `FileViewerView.vue` | 标注列表多选 + 浮动批量工具栏 |

#### 交互
- 行左侧复选框 + Shift 范围 / Cmd 离散多选
- 选中时浮现工具栏: 「已选 N 条」「改类型」「改置信度」「删除」
- Cmd+A 全选当前页

---

## 4. 撤销/重做

### 4.1 问题
删除/编辑不可逆，误操作无法恢复。

### 4.2 实现（纯前端）

| 文件 | 改动 |
|------|------|
| `composables/useUndoRedo.ts` | 操作栈模型，max 20 步，record/undo/redo |
| `composables/useKeyboardShortcuts.ts` | 全局快捷键管理 |

#### 快捷键表

| 快捷键 | 功能 |
|--------|------|
| Ctrl+Z | 撤销 |
| Ctrl+Shift+Z | 重做 |
| Space | 播放/暂停 |
| Delete | 删除选中标注(确认) |
| N | 新建标注模式 |
| E | 编辑选中标注 |
| Tab/Shift+Tab | 跳转下一/上一标注 |
| Escape | 关闭弹窗/取消操作 |
| Ctrl+A | 标注列表全选 |

---

## 5. 快捷手动标注增强

### 5.1 变更

全部在 `FileViewerView.vue` 大 Modal 内：

- **拖拽创建**: 波形上 mousedown-drag 松手 → 迷你类型选择器 popover
- **边界调整**: Alt+悬停标注边缘 → 拖拽调整 start/end
- **双击编辑**: 双击标注 → 迷你编辑 popover (类型/label/置信度)
- **时间指示线**: 鼠标跟随竖线 + 时间标签

---

## 6. 实施顺序

| # | 功能 | 类型 | 预估 |
|---|------|------|------|
| 1 | 撤销/重做 + 快捷键 | 纯前端 | 中 |
| 2 | 检测预览与审核模式 | 前后端 | 大 |
| 3 | 区域选择 + 智能重检测 | 前后端 | 大 |
| 4 | 批量标注操作 | 前后端 | 中 |
| 5 | 快捷手动标注增强 | 前端 canvas | 中 |

---

## 7. 验证标准

- 后端 pytest: 新增 endpoint 测试全部通过
- 前端 vitest: 新增 composable/store 测试全部通过
- 前端 vue-tsc: 无新增类型错误
- **chrome-devtools 实机验证**: 上传真实心音文件 → 检测 → 审核/区域重检/批量修正/撤销 → 确认 BPM 正确
- 文档: `docs/features.md` 同步更新 API 列表和组件说明
