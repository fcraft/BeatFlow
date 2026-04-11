# TODO: ECG/PCG 病理性质检测功能

> 状态：待开发  
> 优先级：高  
> 创建时间：2026-04-11

## 背景

当前 BeatFlow 的 `analysis/` 模块仅能检测信号**成分**（QRS/P/T/S1/S2 位置），**无法识别病理性质**（早搏、ST 抬高、房颤、杂音分类等）。需通过集成开源预训练深度学习模型，为平台新增自动化病理分类能力。

---

## 任务清单

### 阶段一：ECG 病理检测（优先级 1）

- [ ] **1.1 引入依赖**
  - `pyproject.toml` 新增 `torch`（PyTorch）和 `huggingface-hub` 依赖
  - PyTorch 作为**可选依赖**，未安装时病理检测 API 返回 501，不影响现有功能

- [ ] **1.2 模型管理器** — `backend/app/analysis/model_manager.py`
  - 统一管理模型权重下载（HuggingFace Hub）、路径管理（`backend/models/`）、版本追踪
  - lazy-loading 单例模式 + `threading.Lock` 保证线程安全
  - 提供 `get_ecg_model()` / `get_pcg_model()` 接口

- [ ] **1.3 ECG 分类模块** — `backend/app/analysis/ecg_classifier.py`
  - 集成 `zackyabd/clinical-ecg-classifier`（HuggingFace，71 种分类，PyTorch）
  - 信号预处理：重采样 500→100Hz（`scipy.signal.resample_poly`），截取 10s 窗口，12 导联适配
  - 单导联 ECG 处理：复制到 12 通道，标注 `single_lead_padded`，降低置信度权重
  - 滑动窗口（10s 步长）+ 结果聚合，支持长信号
  - 输出 71 类概率（按降序），覆盖：
    - 节律异常：AF / AFL / 窦速 / 窦缓 / PVC / VT
    - 传导障碍：LBBB / RBBB / AVB 各度
    - 缺血梗死：ST-T 改变 / AMI / IMI
    - 肥大：LVH / RVH / LAE / RAE

- [ ] **1.4 后端 API 端点**
  - `files.py` 新增 `POST /files/{file_id}/pathology-detect`
  - 复用现有文件读取 + 信号加载逻辑
  - 推理通过 `run_in_executor` 在线程池异步执行，不阻塞事件循环
  - 结果写入 `AnalysisResult`（`analysis_type = "ecg_pathology"`）
  - `result_data` 结构：`{predictions: [{code, name, category, probability}...], model_version, input_info, processing_time_ms}`

- [ ] **1.5 数据模型扩展**
  - `AnalysisResult.analysis_type` 新增 `"ecg_pathology"` / `"pcg_pathology"`
  - `AnnotationType` 枚举扩展（如需）

- [ ] **1.6 后端单元测试** — `backend/tests/test_pathology_classifier.py`
  - 测试预处理（重采样 / 分窗 / 导联适配）
  - 测试模型加载失败降级（PyTorch 未安装时返回 501）
  - 测试推理结果格式化

### 阶段二：PCG 异常检测（优先级 2）

- [ ] **2.1 PCG 分类模块** — `backend/app/analysis/pcg_classifier.py`
  - 基于 PhysioNet/CinC 2016 Challenge 方案
  - Mel 频谱特征提取 + Normal/Abnormal 二分类
  - 输出：正常/异常概率

- [ ] **2.2 PCG API 集成**
  - 复用 `POST /files/{file_id}/pathology-detect`，根据文件类型自动路由到 ECG 或 PCG 分类器
  - 结果写入 `AnalysisResult`（`analysis_type = "pcg_pathology"`）

- [ ] **2.3 PCG 杂音细分类（长期目标）**
  - 利用仿真引擎合成标注数据，训练杂音细分类模型（7 种杂音类型）
  - 替代二分类模型，提供更精细的诊断信息

### 阶段三：前端展示

- [ ] **3.1 病理检测结果面板** — `frontend/src/components/project/PathologyResultPanel.vue`
  - 按置信度排序的分类列表
  - 概率条形图可视化
  - 风险等级标注（高 / 中 / 低）
  - 检测元信息（模型版本 / 处理时间）

- [ ] **3.2 检测触发入口**
  - `SyncViewerView.vue` 文件详情区域新增"病理检测"按钮
  - 调用 API 后展示结果面板

---

## 技术方案要点

### 推荐模型

| 信号 | 模型 | 分类数 | 大小 | 输入格式 | 性能 |
|------|------|--------|------|----------|------|
| ECG | `zackyabd/clinical-ecg-classifier` | 71 类 | ~166MB | `[batch, 12, 1000]` @ 100Hz | Macro AUC 0.9424 |
| PCG | CinC 2016 方案 | 2 类 | 轻量 | Mel 频谱 | 待定 |

### 架构设计

```
前端 → POST /files/{id}/pathology-detect → FastAPI Endpoint
  → 文件类型判断 → ECG: ecg_classifier / PCG: pcg_classifier
  → 信号加载 + 预处理 → 模型推理（线程池）→ 结果写入 DB → 返回 JSON
```

### 性能预估

- PyTorch CPU 推理：单次 ECG 分类约 100-300ms
- 模型首次加载：约 1-3s（166MB），后续共享内存中实例
- 长信号：滑动窗口 + 结果聚合

### 依赖变更

```toml
# backend/pyproject.toml 新增
torch = ">=2.0"           # ECG/PCG 病理分类模型推理
huggingface-hub = ">=0.20" # 模型权重自动下载
```

### 向后兼容

- PyTorch 作为**可选依赖**，未安装时 API 返回 `501 Not Implemented`
- 现有成分检测功能完全不受影响

---

## 备选方案（调研记录）

| 方案 | 项目 | 优点 | 缺点 |
|------|------|------|------|
| A | HeartKit (Ambiq AI) | pip install, Model Zoo | 需 Python >=3.12, TensorFlow 依赖 |
| B | clinical-ecg-classifier ⭐ | 71 类, PyTorch, AUC 0.94 | 需引入 PyTorch |
| C | HuBERT-ECG | 164 类, 最广覆盖 | CC BY-NC 非商用, 需微调 |
| D | HeartGPT | MIT 协议, 可解释 | 分类有限, 偏研究 |
