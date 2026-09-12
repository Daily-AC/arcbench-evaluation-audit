# ARC-Bench 攻防测试 · 1314520

本仓库公开本账号的评测复现操作、最小控制代码和脱敏证据，供主办方核查。
这些程序是**固定公开答案控制**。模型最多负责选择模板，不负责生成应用源码；其榜单结果不代表通用 Agent 能力。

已实测的历史控制：固定答案加两个极短分类调用，通过两项 Smoke，合计 **50 Token、CNY 0.000072**，总榜效率 **1,388,888.8889**。零调用 Counter 也通过，但效率为 `null`。
原始运行：[零调用](https://arc-bench.com/runs/5328c93e9838)、[分类 Counter](https://arc-bench.com/runs/6076600e642d)、[分类 Dice](https://arc-bench.com/runs/03d81f1d24ed)。历史记录见 [evidence](evidence/historical-controls.json)。

这里提供独立可运行的后继版本，覆盖当前公开的 Smoke、Smoke Evolution 和 Ticket 注册登录用例。
本地原版公开测试 **16/16** 通过，Ticket **10/10**。本仓库版本的官方复验结果将在取得后单独记录。

## 构建与运行

```sh
python3 -m pip install -r requirements.txt
python3 scripts/build_package.py --output dist/攻防测试-1314520.zip --profile router --marker 1314520
```

将 ZIP 通过平台正常上传流程提交，名称明确使用 `攻防测试-1314520` 前缀。平台调用：

```sh
python3 main.py REQUIREMENT_DIRECTORY --output-dir APPLICATION_DIRECTORY
```

`router` 使用平台提供的 `OPENAI_BASE_URL`、`OPENAI_API_KEY`、`MODEL`，仅向主办方网关发送一次分类请求，最多四个输出 Token。
`zero` 安装固定答案且完全不调用模型。打包本身不启动线上运行，也不携带账号凭据。
`bindings.json` 以规范化需求文档哈希限定五个公开输入；未知需求会退出。

代码：`agent.py` 是入口；`answers/` 是预置页面；`runtime/` 是最小应用服务；`scripts/build_package.py` 通过明确文件清单打包。
Ticket 只是这组公开验收的演示实现；用户与会话保存在当前进程中，不是生产认证系统。

## 本地公开测试

从平台取得原始需求目录与公开测试后，可以使用已经安装的 Playwright 1.57.0 和浏览器：

```sh
python3 scripts/verify_public.py \
  --inputs /path/to/public-inputs --checks /path/to/public-checks \
  --output runs/local-check \
  --playwright /path/to/node_modules/@playwright/test \
  --browser /path/to/chrome
```

验证器保留测试原始字节，并检查实际执行的用例数量。本地浏览器通过不替代官方结果。
公开需求与测试来源记录在 `bindings.json`，本仓库没有复制私人聊天截图、账号凭据或完整私有工程。

## 彩蛋数值与真实计费

`1314520` 是提交名和审计元数据中的标记。代码不写入或覆盖平台分数。
两个候选数字都小于 2^53，可以由 binary64 精确表示；限制在费用公式，不在整数容量。

| 目标效率 | 100% 通过率所需费用（CNY） |
|---|---:|
| 1145141919810 | 约 0.00000000008732542 |
| 1314520 | 约 0.00007607339561208654 |

按当前观察到的六位小数费用记录，邻近 CNY 0.000076 对应效率 **1,315,789.4737**，不是 1,314,520。
实际指标必须以服务端回传为准，不能用声明值冒充。历史效率字段是百分制通过率除以费用，也不是实际完成的百万任务数。

## 给主办方的结论

公开固定题可以直接缓存答案，单独加密服务端测试文件无法消除这一现象。
若希望衡量生成或泛化，应在冻结提交后使用新的任务或语义变化，并分别披露缓存、模型路由与模型生成。
运行时保密则需要隔离候选程序与验收文件、密钥和评分输出；网络限制仍需考虑日志和产物这一允许的返回通道。
本记录只证明一种可行路径，不判断其他队伍使用了什么方法。
