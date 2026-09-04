"""大语言模型客户端：读取 .env 密钥，经 OpenAI SDK 调用 Agnes AI 生成路况分析。

用法:
    client = LLMClient()   # 自动从项目根目录 .env 加载密钥
    ok, text, err = client.analyze(traffic_stats)

分析输入包含目标列表 JSON（同步保存到项目根目录 traffic_targets.json）
与流量统计摘要。无 Qt 依赖，可在后台线程中安全调用。
"""
import json
import os

from app.config import Config


def _load_env():
    """加载项目根目录的 .env 文件，返回是否成功。"""
    try:
        from dotenv import load_dotenv
        # 本文件位于 app/backend/ 下，向上三级到项目根目录
        project_root = os.path.dirname(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        env_path = os.path.join(project_root, '.env')
        if os.path.exists(env_path):
            load_dotenv(dotenv_path=env_path, override=False)
            return True
    except ImportError:
        pass
    return False


_load_env()


# ---- Prompt 模板 ----
SYSTEM_PROMPT = """你是一位专业的智能交通路况分析专家。你的职责是根据视频监控系统的目标检测与流量统计数据，分析路况状况并给出专业建议。

输出要求：
- 使用中文回答
- 使用 Markdown 格式输出
- 分析应基于提供的数据，避免主观臆断
- 建议应具体可执行"""

USER_PROMPT_TEMPLATE = """## 一、目标列表（JSON）

以下为视频检测期间所有进入过监控区域的目标记录：

```json
{target_list_json}
```

## 二、交通统计信息

{traffic_summary}

---

请基于以上数据，从以下四个维度进行专业分析：

### 1. 交通状况评估
判断当前路段处于「畅通」「缓行」还是「拥堵」状态，并给出判断依据。

### 2. 异常情况识别
识别是否存在异常停车、密集排队、行人横穿、非机动车违规占道等异常行为。

### 3. 原因分析
结合目标类别分布、区域聚集程度、停留时间等数据，分析导致当前路况的可能原因。

### 4. 改善建议
针对所发现问题，提出信号配时优化、车道规划、限速建议、区域管控等具体改善措施。"""


class LLMClient:
    """大语言模型客户端（Agnes AI 接口，通过 OpenAI SDK 调用）。"""

    def __init__(self):
        self.config = Config()
        self.api_key = os.environ.get('AGNES_API_KEY', '')
        self.base_url = os.environ.get('AGNES_BASE_URL', '')
        self.model = self.config.get('llm', 'model', default='agnes-2.0-flash')
        self.timeout = 30  # 请求超时秒数
        self._class_names_cn = self.config.get('classes', default={}) or {}
        # 延迟创建客户端，避免密钥未配置时报错
        self._client = None

    @property
    def is_configured(self):
        """检查 API 密钥和地址是否已配置。"""
        return bool(self.api_key and self.base_url)

    def _get_client(self):
        """延迟创建 OpenAI 客户端实例。"""
        if self._client is None and self.is_configured:
            from openai import OpenAI
            self._client = OpenAI(
                api_key=self.api_key,
                base_url=self.base_url,
                timeout=self.timeout,
            )
        return self._client

    def _cn_name(self, class_id):
        """类别 ID → 中文名称。"""
        return self._class_names_cn.get(class_id, str(class_id))

    def _save_target_list_json(self, traffic_stats):
        """从最新统计快照提取目标列表，保存为 JSON 文件并返回 JSON 字符串。

        输出结构: [{"目标ID", "类别", "当前位置", "停留时间(秒)", "置信度"}]
        """
        latest_stats = traffic_stats[-1] if traffic_stats else {}
        track_status = latest_stats.get('track_status', {})

        targets = []
        for tid in sorted(track_status):
            info = track_status[tid]
            targets.append({
                "目标ID": int(tid),
                "类别": self._cn_name(info.get('class_id', 0)),
                "当前位置": "区域内" if info.get('inside') else "离开区域",
                "停留时间(秒)": round(info.get('dwell', 0.0), 1),
                "置信度": round(info.get('confidence', 0.0), 3),
            })

        json_str = json.dumps(targets, ensure_ascii=False, indent=2)

        project_root = os.path.dirname(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        try:
            with open(os.path.join(project_root, 'traffic_targets.json'),
                      'w', encoding='utf-8') as f:
                f.write(json_str)
        except Exception:
            pass  # 文件写入失败不影响 LLM 调用
        return json_str

    def _build_traffic_summary(self, stats_snapshots):
        """将多帧统计数据汇总为结构化文字描述。"""
        if not stats_snapshots:
            return "暂无交通统计数据。"

        latest = stats_snapshots[-1]
        total_inflow = latest.get('inflow', 0)
        total_outflow = latest.get('outflow', 0)
        flow_rate = latest.get('flow_rate', 0)
        inside = latest.get('current_inside', 0)
        avg_dwell = latest.get('avg_dwell', 0)
        video_time = latest.get('current_time', 0)
        total_time = latest.get('total_time', 0)
        window_sec = latest.get('window_seconds', 1.0)
        system_time = latest.get('system_time', '')

        lines = [
            f"- 监测时长: {int(total_time // 60):02d}:{int(total_time % 60):02d}",
            f"- 当前时刻: {system_time} (视频第 {int(video_time // 60):02d}:{int(video_time % 60):02d})",
            f"- 当前区域内数量: {inside} 个",
            f"- 流量速率: {flow_rate} 个/{window_sec:.0f}秒",
            f"- 累计流入: {total_inflow} 个",
            f"- 累计流出: {total_outflow} 个",
            f"- 平均停留时间: {avg_dwell:.1f} 秒",
        ]

        if len(stats_snapshots) > 1:
            peak_inside = max(s.get('current_inside', 0) for s in stats_snapshots)
            peak_flow = max(s.get('flow_rate', 0) for s in stats_snapshots)
            lines.append(f"- 峰值: 区域内最高 {peak_inside} 个, 流量最高 {peak_flow}")

        return '\n'.join(lines)

    def analyze(self, traffic_stats):
        """调用 LLM 分析交通状况。

        参数:
            traffic_stats: 统计快照列表（多个时间点的 stats dict，含 track_status）

        返回:
            (success: bool, analysis_text: str, error_msg: str)
        """
        if not self.is_configured:
            return False, "", "API 未配置：请在项目根目录 .env 文件中设置 AGNES_API_KEY 和 AGNES_BASE_URL"

        client = self._get_client()
        if client is None:
            return False, "", "OpenAI 客户端初始化失败"

        # 构造 prompt：目标列表 JSON + 流量统计
        target_list_json = self._save_target_list_json(traffic_stats)
        traffic_summary = self._build_traffic_summary(traffic_stats)
        user_prompt = USER_PROMPT_TEMPLATE.format(
            target_list_json=target_list_json,
            traffic_summary=traffic_summary,
        )

        try:
            response = client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=0.7,
                max_tokens=4096,
            )
            content = response.choices[0].message.content
            if content:
                return True, content.strip(), ''
            return False, "", "API 返回空内容"
        except Exception as e:
            return False, "", f"API 调用失败: {str(e)}"
