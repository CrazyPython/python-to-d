from decorator import generate_dlang_code


def test_generate_dlang_code() -> None:
    def empty(a) -> int:
        pass

    s = generate_dlang_code(empty)

    def nonce_list():
        a = [1, 'two', 3, '4']

    s = generate_dlang_code(nonce_list)

    def empty_list():
        a = []
        b = 1
        d: int = 1
        e: list[int] = [1]
        a = 1

    s = generate_dlang_code(empty_list)
    pass

# @(dlang_options=, )

#Automatic Type Inference#
#MonkeyType
