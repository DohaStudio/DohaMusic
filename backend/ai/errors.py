"""Provider-independent music generation failures."""


class MusicGenerationError(RuntimeError):
    code = "AI_INFERENCE_FAILED"


class AIProviderNotConfiguredError(MusicGenerationError):
    code = "AI_PROVIDER_NOT_CONFIGURED"


class AIDependencyNotInstalledError(MusicGenerationError):
    code = "AI_DEPENDENCY_NOT_INSTALLED"


class AIModelNotFoundError(MusicGenerationError):
    code = "AI_MODEL_NOT_FOUND"


class AIModelLoadError(MusicGenerationError):
    code = "AI_MODEL_LOAD_FAILED"


class AIInferenceError(MusicGenerationError):
    code = "AI_INFERENCE_FAILED"


class AIOutOfMemoryError(MusicGenerationError):
    code = "AI_OUT_OF_MEMORY"


class AIOutputNotCreatedError(MusicGenerationError):
    code = "AI_OUTPUT_NOT_CREATED"


class AIAudioDecodeError(MusicGenerationError):
    code = "AI_AUDIO_DECODE_FAILED"


class AITimeoutError(MusicGenerationError):
    code = "AI_TIMEOUT"
