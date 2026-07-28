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


class StemSeparationError(RuntimeError):
    code = "STEM_SEPARATION_FAILED"


class StemProviderNotConfiguredError(StemSeparationError):
    code = "STEM_PROVIDER_NOT_CONFIGURED"


class StemDependencyNotInstalledError(StemSeparationError):
    code = "STEM_DEPENDENCY_NOT_INSTALLED"


class StemModelNotFoundError(StemSeparationError):
    code = "STEM_MODEL_NOT_FOUND"


class StemModelLoadError(StemSeparationError):
    code = "STEM_MODEL_LOAD_FAILED"


class StemInferenceError(StemSeparationError):
    code = "STEM_SEPARATION_FAILED"


class StemOutOfMemoryError(StemSeparationError):
    code = "STEM_OUT_OF_MEMORY"


class StemOutputNotCreatedError(StemSeparationError):
    code = "STEM_OUTPUT_NOT_CREATED"


class StemAudioDecodeError(StemSeparationError):
    code = "STEM_AUDIO_DECODE_FAILED"


class StemTimeoutError(StemSeparationError):
    code = "STEM_TIMEOUT"
