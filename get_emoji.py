from typing import Optional

EMOJI_CODE = {200: 'U+26C8',
              201: 'U+26C8',
              202: 'U+26C8',
              210: 'U+1F329',
              211: 'U+1F329',
              212: 'U+1F329',
              221: 'U+1F329',
              230: 'U+26C8',
              231: 'U+26C8',
              232: 'U+26C8',
              301: 'U+1F327',
              302: 'U+1F327',
              310: 'U+1F327',
              311: 'U+1F327',
              312: 'U+1F327',
              313: 'U+1F327',
              314: 'U+1F327',
              321: 'U+1F327',
              500: 'U+1F327',
              501: 'U+1F327',
              502: 'U+1F327',
              503: 'U+1F327',
              504: 'U+1F327',
              511: 'U+1F327',
              520: 'U+1F327',
              521: 'U+1F327',
              522: 'U+1F327',
              531: 'U+1F327',
              600: 'U+1F328',
              601: 'U+1F328',
              602: 'U+1F328',
              611: 'U+1F328',
              612: 'U+1F328',
              613: 'U+1F328',
              615: 'U+1F328',
              616: 'U+1F328',
              620: 'U+1F328',
              621: 'U+1F328',
              622: 'U+1F328',
              701: 'U+1F32B',
              711: 'U+1F32B',
              721: 'U+1F32B',
              731: 'U+1F32B',
              741: 'U+1F32B',
              751: 'U+1F32B',
              761: 'U+1F32B',
              762: 'U+1F32B',
              771: 'U+1F32B',
              781: 'U+1F32B',
              800: 'U+2600',
              801: 'U+1F324',
              802: 'U+2601',
              803: 'U+2601',
              804: 'U+2601'}


def get_emoji(code: int) -> Optional[str]:
    emoji_code = EMOJI_CODE.get(code)
    if emoji_code:
        return get_emoji_str(emoji_code)
    return None


def get_emoji_str(emoji_code: str) -> str:
    return chr(int(emoji_code.lstrip("U+").zfill(8), 16))


if __name__ == '__main__':
    for code in EMOJI_CODE:
        print(get_emoji(code))
