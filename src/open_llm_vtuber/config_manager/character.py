# config_manager/character.py
from pydantic import Field, field_validator
from typing import Dict, ClassVar
from .i18n import I18nMixin, Description
from .asr import ASRConfig
from .tts import TTSConfig
from .vad import VADConfig
from .tts_preprocessor import TTSPreprocessorConfig

from .agent import AgentConfig


class EmotionLearningConfig(I18nMixin):
    """Configuration for emotion learning."""

    enabled: bool = Field(False, alias="enabled")
    storage_dir: str = Field("emotion_memory", alias="storage_dir")
    decay: float = Field(0.92, alias="decay")
    min_confidence: float = Field(0.1, alias="min_confidence")
    max_recent_events: int = Field(5, alias="max_recent_events")
    include_state: bool = Field(True, alias="include_state")
    include_habits: bool = Field(True, alias="include_habits")
    include_recent_events: bool = Field(True, alias="include_recent_events")
    prompt_max_items: int = Field(3, alias="prompt_max_items")

    DESCRIPTIONS: ClassVar[Dict[str, Description]] = {
        "enabled": Description(en="Enable emotion learning", zh="启用情绪学习"),
        "storage_dir": Description(
            en="Directory for per-character emotion memory", zh="每角色情绪记忆目录"
        ),
        "decay": Description(en="Decay factor per turn", zh="每轮衰减系数"),
        "min_confidence": Description(
            en="Minimum confidence threshold", zh="最小置信度阈值"
        ),
        "max_recent_events": Description(
            en="Max recent events to store", zh="最近事件最大数量"
        ),
        "include_state": Description(
            en="Include mood state in prompt", zh="在提示词中包含情绪状态"
        ),
        "include_habits": Description(
            en="Include expression habits in prompt", zh="在提示词中包含表达习惯"
        ),
        "include_recent_events": Description(
            en="Include recent emotional cues in prompt",
            zh="在提示词中包含最近情绪线索",
        ),
        "prompt_max_items": Description(
            en="Max items to list in prompt", zh="提示词中最大条目数"
        ),
    }


class CharacterConfig(I18nMixin):
    """Character configuration settings."""

    conf_name: str = Field(..., alias="conf_name")
    conf_uid: str = Field(..., alias="conf_uid")
    live2d_model_name: str = Field(..., alias="live2d_model_name")
    character_name: str = Field(default="", alias="character_name")
    human_name: str = Field(default="Human", alias="human_name")
    avatar: str = Field(default="", alias="avatar")
    persona_prompt: str = Field(..., alias="persona_prompt")
    emotion_learning_config: EmotionLearningConfig = Field(
        default=EmotionLearningConfig(), alias="emotion_learning_config"
    )
    agent_config: AgentConfig = Field(..., alias="agent_config")
    asr_config: ASRConfig = Field(..., alias="asr_config")
    tts_config: TTSConfig = Field(..., alias="tts_config")
    vad_config: VADConfig = Field(..., alias="vad_config")
    tts_preprocessor_config: TTSPreprocessorConfig = Field(
        ..., alias="tts_preprocessor_config"
    )

    DESCRIPTIONS: ClassVar[Dict[str, Description]] = {
        "conf_name": Description(
            en="Name of the character configuration", zh="角色配置名称"
        ),
        "conf_uid": Description(
            en="Unique identifier for the character configuration",
            zh="角色配置唯一标识符",
        ),
        "live2d_model_name": Description(
            en="Name of the Live2D model to use", zh="使用的Live2D模型名称"
        ),
        "character_name": Description(
            en="Name of the AI character in conversation", zh="对话中AI角色的名字"
        ),
        "persona_prompt": Description(
            en="Persona prompt. The persona of your character.", zh="角色人设提示词"
        ),
        "emotion_learning_config": Description(
            en="Emotion learning configuration", zh="情绪学习配置"
        ),
        "agent_config": Description(
            en="Configuration for the conversation agent", zh="对话代理配置"
        ),
        "asr_config": Description(
            en="Configuration for Automatic Speech Recognition", zh="语音识别配置"
        ),
        "tts_config": Description(
            en="Configuration for Text-to-Speech", zh="语音合成配置"
        ),
        "vad_config": Description(
            en="Configuration for Voice Activity Detection", zh="语音活动检测配置"
        ),
        "tts_preprocessor_config": Description(
            en="Configuration for Text-to-Speech Preprocessor",
            zh="语音合成预处理器配置",
        ),
        "human_name": Description(
            en="Name of the human user in conversation", zh="对话中人类用户的名字"
        ),
        "avatar": Description(
            en="Avatar image path for the character", zh="角色头像图片路径"
        ),
    }

    @field_validator("persona_prompt")
    def check_default_persona_prompt(cls, v):
        if not v:
            raise ValueError(
                "Persona_prompt cannot be empty. Please provide a persona prompt."
            )
        return v

    @field_validator("character_name")
    def set_default_character_name(cls, v, values):
        if not v and "conf_name" in values:
            return values["conf_name"]
        return v
