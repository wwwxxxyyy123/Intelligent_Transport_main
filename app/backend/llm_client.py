"""大语言模型客户端：读取 .env 中的 API 密钥，通过 OpenAI SDK 调用 Agnes AI 接口。

用法:
    from app.backend.llm_client import LLMClient
    client = LLMClient()  # 自动从项目根目录 .env 加载密钥
    result = client.analyze(detections, traffic_stats)

设计要点：
- 使用 python-dotenv 显式指定项目根目录 .env 路径，避免 cwd 依赖
- 使用 OpenAI SDK 调用 OpenAI 兼容接口（Agnes AI）
- 异常处理完善：网络错误、密钥缺失、响应格式异常均有清晰报错
- 独立模块，无 Qt 依赖，可在后台线程中安全调用
"""
import os

from app.config import Config


# ---- 加载 .env ----
def _load_env():
    """显式加载项目根目录的 .env 文件，返回是否加载成功。"""
    try:
        from dotenv import load_dotenv
        # llm_client.py 位于 app/backend/ 下，需向上三级到项目根目录
        project_root = os.path.dirname(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        env_path = os.path.join(project_root, '.env')
        if os.path.exists(env_path):
            load_dotenv(dotenv_path=env_path, override=False)
            return True
    except ImportError:
        pass
    return False


# 模块加载时立即尝试读取 .env
_load_env()


# ---- Prompt 模板 ----
SYSTEM_PROMPT = """你是一位专业的交通路况分析专家，擅长根据目标检测数据和交通统计信息分析路况并给出改进建议。请用中文回答，并使用 Markdown 格式输出。"""

USER_PROMPT_TEMPLATE = """以下是当前视频监控的检测与统计数据，请分析当前交通状况并给出建议：

【检测结果汇总】
{detection_summary}

【交通统计信息】
{traffic_summary}

请从以下几个方面进行分析（使用 Markdown 格式）：
1. **当前交通状况评估**（畅通/缓行/拥堵）
2. **异常情况识别**（如异常停车、密集排队、行人横穿等）
3. **可能的原因分析**
4. **改善建议**（如交通信号配时、车道规划、限速建议等）

请给出简洁明了的分析和建议，使用 Markdown 标题、列表、粗体等格式。"""


class LLMClient:
    """大语言模型客户端（Agnes AI 接口，通过 OpenAI SDK 调用）。"""

    def __init__(self):
        self.config = Config()
        self.api_key = os.environ.get('AGNES_API_KEY', '')
        self.base_url = os.environ.get('AGNES_BASE_URL', '')
        self.model = self.config.get('llm', 'model', default='agnes-2.0-flash')
        self.timeout = 30  # 请求超时秒数
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

    def _build_detection_summary(self, detections):
        """将检测结果列表汇总为文字描述。"""
        if not detections:
            return "当前未检测到任何目标。"

        # 按类别统计
        class_counts = {}
        for det in detections:
            name = det.get('class_name', '未知')
            class_counts[name] = class_counts.get(name, 0) + 1

        lines = [f"共检测到 {len(detections)} 个目标："]
        for name, count in class_counts.items():
            lines.append(f"  - {name}: {count} 个")

        # 列出部分目标详情（最多10个）
        lines.append("\n目标详情（前10个）：")
        for i, det in enumerate(detections[:10]):
            cid = det.get('track_id', det.get('id', i))
            cls = det.get('class_name', '未知')
            conf = det.get('confidence', 0)
            lines.append(f"  #{cid}: {cls} (置信度 {conf:.2f})")

        return '\n'.join(lines)

    def _build_traffic_summary(self, stats_snapshots):
        """将多帧统计数据汇总为文字描述。"""
        if not stats_snapshots:
            return "暂无交通统计数据。"

        # 取最新一帧作为当前状态
        latest = stats_snapshots[-1]
        # 计算最近窗口内的累积
        total_inflow = latest.get('inflow', 0)
        total_outflow = latest.get('outflow', 0)
        flow_rate = latest.get('flow_rate', 0)
        inside = latest.get('current_inside', 0)
        avg_dwell = latest.get('avg_dwell', 0)
        cur_dwell = latest.get('cur_avg_dwell', 0)
        video_time = latest.get('current_time', 0)
        total_time = latest.get('total_time', 0)

        lines = [
            f"视频时长: {int(total_time // 60):02d}:{int(total_time % 60):02d}",
            f"当前时刻: {int(video_time // 60):02d}:{int(video_time % 60):02d}",
            f"当前流量: {flow_rate} (窗口时长内流入区域的车辆数)",
            f"区域内数量: {inside} 辆",
            f"累计流入: {total_inflow} 辆",
            f"累计流出: {total_outflow} 辆",
            f"平均停留时间: {avg_dwell:.1f} 秒",
            f"当前停留时间: {cur_dwell:.1f} 秒",
        ]

        # 计算检测期间的峰值
        if len(stats_snapshots) > 1:
            peak_inside = max(s.get('current_inside', 0) for s in stats_snapshots)
            peak_flow = max(s.get('flow_rate', 0) for s in stats_snapshots)
            lines.append(f"\n检测期间峰值: 区域内最高 {peak_inside} 辆, 流量最高 {peak_flow}")

        return '\n'.join(lines)

    def analyze(self, detections, traffic_stats):
        """调用 LLM 分析交通状况。

        参数:
            detections: 当前帧的检测结果列表
            traffic_stats: 统计快照列表（多个时间点的 stats dict）

        返回:
            (success: bool, analysis_text: str, error_msg: str)
        """
        if not self.is_configured:
            return False, "", "API 未配置：请在项目根目录 .env 文件中设置 AGNES_API_KEY 和 AGNES_BASE_URL"

        client = self._get_client()
        if client is None:
            return False, "", "OpenAI 客户端初始化失败"

        # 构造 prompt
        det_summary = self._build_detection_summary(detections)
        traf_summary = self._build_traffic_summary(traffic_stats)
        user_prompt = USER_PROMPT_TEMPLATE.format(
            detection_summary=det_summary,
            traffic_summary=traf_summary,
        )

        try:
            response = client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=0.7,
                max_tokens=1024,
            )
            content = response.choices[0].message.content
            if content:
                return True, content.strip(), ''
            return False, "", "API 返回空内容"
        except Exception as e:
            return False, "", f"API 调用失败: {str(e)}"
