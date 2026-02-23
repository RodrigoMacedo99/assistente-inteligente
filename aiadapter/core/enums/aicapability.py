from enum import Enum


class AICapability(Enum):
    '''
    Interface que define as diferentes capacidades que um provedor de IA pode suportar.
    '''
    TEXT = "text"
    EMBEDDINGS = "embeddings"
    VISION = "vision"
    FUNCTION_CALLING = "function_calling"
    AUDIO = "audio"
    VIDEO = "video"