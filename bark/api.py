from typing import Dict, Optional, Union
import re
import numpy as np
import tqdm
from .generation import generate_text_semantic_new, generate_coarse_new, generate_fine_new, codec_decode_new, codec_decode, generate_coarse, generate_fine, generate_text_semantic, SAMPLE_RATE

def text_to_semantic_new(
    text: str,
    history_prompt: Optional[Union[str, dict]] = None,
    temp: float = 0.7,
    silent: bool = False,
    allow_early_stop: bool = True,
    min_eos_p: float = 0.2
):
    """Generate semantic array from text.

    Args:
        text: text to be turned into audio
        history_prompt: history choice for audio cloning
        temp: generation temperature (1.0 more diverse, 0.0 more conservative)
        silent: disable progress bar
        allow_early_stop: (Added in new) set to False to generate until the limit
        min_eos_p: (Added in new) Generation stopping likelyness, Lower means more likely to stop.
        progress: (Added in new) Gradio progress bar.

    Returns:
        numpy semantic array to be fed into `semantic_to_waveform`
    """
    x_semantic = generate_text_semantic_new(
        text,
        history_prompt=history_prompt,
        temp=temp,
        silent=silent,
        use_kv_caching=True,
        allow_early_stop=allow_early_stop,
        min_eos_p=min_eos_p
    )
    return x_semantic

def text_to_semantic(
    text: str,
    history_prompt: Optional[Union[Dict, str]] = None,
    temp: float = 0.7,
    silent: bool = False,
):
    """Generate semantic array from text.

    Args:
        text: text to be turned into audio
        history_prompt: history choice for audio cloning
        temp: generation temperature (1.0 more diverse, 0.0 more conservative)
        silent: disable progress bar

    Returns:
        numpy semantic array to be fed into `semantic_to_waveform`
    """
    x_semantic = generate_text_semantic(
        text,
        history_prompt=history_prompt,
        temp=temp,
        silent=silent,
        use_kv_caching=True
    )
    return x_semantic

def semantic_to_waveform_new(
    semantic_tokens: np.ndarray,
    history_prompt: Optional[Union[str, dict]] = None,
    temp: float = 0.7,
    silent: bool = False,
    output_full: bool = False,
    skip_fine: bool = False,
    decode_on_cpu: bool = False
):
    """Generate audio array from semantic input.

    Args:
        semantic_tokens: semantic token output from `text_to_semantic`
        history_prompt: history choice for audio cloning
        temp: generation temperature (1.0 more diverse, 0.0 more conservative)
        silent: disable progress bar
        output_full: return full generation to be used as a history prompt
        skip_fine: (Added in new) Skip converting coarse to fine
        decode_on_cpu: (Added in new) Move everything to cpu when decoding, useful for decoding huge audio files on medium vram
        progress: (Added in new) Gradio progress bar.

    Returns:
        numpy audio array at sample frequency 24khz
    """
    coarse_tokens = generate_coarse_new(
        semantic_tokens,
        history_prompt=history_prompt,
        temp=temp,
        silent=silent,
        use_kv_caching=True
    )
    if not skip_fine:
        fine_tokens = generate_fine_new(
            coarse_tokens,
            history_prompt=history_prompt,
            temp=0.5
        )
    else:
        fine_tokens = coarse_tokens
    audio_arr = codec_decode_new(fine_tokens, decode_on_cpu)
    if output_full:
        full_generation = {
            "semantic_prompt": semantic_tokens,
            "coarse_prompt": coarse_tokens,
            "fine_prompt": fine_tokens,
        }
        return full_generation, audio_arr
    return audio_arr

def semantic_to_waveform(
    semantic_tokens: np.ndarray,
    history_prompt: Optional[Union[Dict, str]] = None,
    temp: float = 0.7,
    silent: bool = False,
    output_full: bool = False,
):
    """Generate audio array from semantic input.

    Args:
        semantic_tokens: semantic token output from `text_to_semantic`
        history_prompt: history choice for audio cloning
        temp: generation temperature (1.0 more diverse, 0.0 more conservative)
        silent: disable progress bar
        output_full: return full generation to be used as a history prompt

    Returns:
        numpy audio array at sample frequency 24khz
    """
    coarse_tokens = generate_coarse(
        semantic_tokens,
        history_prompt=history_prompt,
        temp=temp,
        silent=silent,
        use_kv_caching=True
    )
    fine_tokens = generate_fine(
        coarse_tokens,
        history_prompt=history_prompt,
        temp=0.5,
    )
    audio_arr = codec_decode(fine_tokens)
    if output_full:
        full_generation = {
            "semantic_prompt": semantic_tokens,
            "coarse_prompt": coarse_tokens,
            "fine_prompt": fine_tokens,
        }
        return full_generation, audio_arr
    return audio_arr


def save_as_prompt(filepath, full_generation):
    assert(filepath.endswith(".npz"))
    assert(isinstance(full_generation, dict))
    assert("semantic_prompt" in full_generation)
    assert("coarse_prompt" in full_generation)
    assert("fine_prompt" in full_generation)
    np.savez(filepath, **full_generation)

def generate_audio(
    text: str,
    history_prompt: Optional[Union[Dict, str]] = None,
    text_temp: float = 0.7,
    waveform_temp: float = 0.7,
    silent: bool = False,
    output_full: bool = False,
):
    """Generate audio array from input text.

    Args:
        text: text to be turned into audio
        history_prompt: history choice for audio cloning
        text_temp: generation temperature (1.0 more diverse, 0.0 more conservative)
        waveform_temp: generation temperature (1.0 more diverse, 0.0 more conservative)
        silent: disable progress bar
        output_full: return full generation to be used as a history prompt

    Returns:
        numpy audio array at sample frequency 24khz
    """
    semantic_tokens = text_to_semantic(
        text,
        history_prompt=history_prompt,
        temp=text_temp,
        silent=silent,
    )
    out = semantic_to_waveform(
        semantic_tokens,
        history_prompt=history_prompt,
        temp=waveform_temp,
        silent=silent,
        output_full=output_full,
    )
    if output_full:
        full_generation, audio_arr = out
        return full_generation, audio_arr
    else:
        audio_arr = out
    return audio_arr

def strict_split(string: str, regex='([.,:;!?\\n])'):
    splits = re.split(regex, string)
    splits_out = []
    last = ''
    for idx, split in enumerate(splits):
        if idx % 2 == 0:
            last = split
        else:
            last += split
            splits_out.append(last)

    if len(splits_out) == 0 or not splits_out[-1] == last:
        splits_out.append(last)

    return splits_out


def non_strict_split(string: str):
    return strict_split(string, '(\\.)')


def long_merge(splits: list[str]):
    limit = 220  # Estimated for normal speaking speed

    out_list = []
    current_str = ''

    for split in splits:
        if len(current_str) + len(split) <= limit:
            current_str += split
        else:
            if current_str:
                out_list.append(current_str)
            current_str = split

    if current_str:
        out_list.append(current_str)

    return out_list


def strict_short(string):
    return strict_split(string)


def strict_long(string):
    return long_merge(strict_split(string))


def non_strict_short(string):
    return non_strict_split(string)


def non_strict_long(string):
    return long_merge(non_strict_split(string))

def generate_audio_new(
    text: str,
    history_prompt: Optional[Union[str, dict]] = None,
    text_temp: float = 0.7,
    waveform_temp: float = 0.7,
    silent: bool = False,
    output_full: bool = False,
    skip_fine: bool = False,
    decode_on_cpu: bool = False,
    allow_early_stop: bool = True,
    min_eos_p: float = 0.2,
    long_gen_silence_secs: float = 0,
    long_gen_re_feed: bool = True,
    gen_prefix: str = '',
    split_type: str = 'non-strict short'
):
    """Generate audio array from input text.

    Args:
        text: text to be turned into audio
        history_prompt: history choice for audio cloning
        text_temp: generation temperature (1.0 more diverse, 0.0 more conservative)
        waveform_temp: generation temperature (1.0 more diverse, 0.0 more conservative)
        silent: disable progress bar
        output_full: return full generation to be used as a history prompt
        skip_fine: (Added in new) Skip converting from coarse to fine
        decode_on_cpu: (Added in new) Decode on cpu
        allow_early_stop: (Added in new) Set to false to continue until the limit is reached
        min_eos_p: (Added in new) Lower values stop the generation earlier.
        long_gen_silence_secs: (Added in new) The amount of silence between clips for long form generations.
        long_gen_re_feed: (Added in new) For longer generations (\n) use the last generated chunk as the prompt for the next. Better continuation at risk of changing voice.
        gen_prefix: (Added in new) A prefix to add to every single generated chunk.
        split_type: (Added in new) The way to split the clips.
        progress: (Added in new) Gradio progress bar.

    Returns:
        numpy audio array at sample frequency 24khz
    """
    silence = np.zeros(int(long_gen_silence_secs * SAMPLE_RATE))
    gen_audio = []
    if text:
        match split_type.casefold():
            case 'manual':
                gen_sections = text.strip().split('\n')
            case 'strict short':
                gen_sections = strict_short(text)
            case 'strict long':
                gen_sections = strict_long(text)
            case 'non-strict short':
                gen_sections = non_strict_short(text)
            case 'non-strict long':
                gen_sections = non_strict_long(text)
            case _:
                print('??? Unknown split method selected. Not splitting.')
                gen_sections = [text]
    else:
        gen_sections = [text]
    print('Generation split into sections:', gen_sections)
    for input_text in tqdm.tqdm(gen_sections, desc='Generation section'):
        if len(input_text) == 0:
            continue
        if gen_prefix:
            input_text = gen_prefix + " " + input_text + " " + gen_prefix
        
        semantic_tokens = text_to_semantic_new(
            input_text,
            history_prompt=history_prompt,
            temp=text_temp,
            silent=silent,
            allow_early_stop=allow_early_stop,
            min_eos_p=min_eos_p
        )
        out = semantic_to_waveform_new(
            semantic_tokens,
            history_prompt=history_prompt,
            temp=waveform_temp,
            silent=silent,
            output_full=True,
            skip_fine=skip_fine,
            decode_on_cpu=decode_on_cpu
        )
        full_generation, gen_audio_new = out
        if long_gen_re_feed:
            history_prompt = full_generation
        gen_audio += [gen_audio_new, silence.copy()]

    gen_audio = np.concatenate(gen_audio)

    if output_full:
        return full_generation, gen_audio
    return gen_audio

