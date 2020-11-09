import pytest
from ..ui import askyesno


@pytest.mark.parametrize(
    "answer,output",
    [
        ("yes", True),
        ("y", True),
        ("YES", True),
        ("Y", True),
        (" yes ", True),
        (" y ", True),
        ("no", False),
        ("n", False),
        ("NO", False),
        ("N", False),
        (" no ", False),
        (" n ", False),
    ],
)
def test_askyesno_direct_answer(mocker, answer, output):
    inputmock = mocker.patch("dandi.support.ui.input", return_value=answer)
    r = askyesno("Is this OK?")
    assert r == output
    inputmock.assert_called_once_with("Is this OK? [y/n] ")


@pytest.mark.parametrize(
    "answers,output",
    [(["foo", "y"], True), (["", "n"], False), (["yesno", "yes!", "YES"], True)],
)
def test_askyesno_invalids(capsys, mocker, answers, output):
    answeriter = iter(answers)
    inputmock = mocker.patch(
        "dandi.support.ui.input", side_effect=lambda _: next(answeriter)
    )
    r = askyesno("Is this OK?")
    assert r == output
    assert inputmock.call_args_list == [mocker.call("Is this OK? [y/n] ")] * len(
        answers
    )
    assert capsys.readouterr().out == "Please answer 'y'/'yes'/'n'/'no'.\n" * (
        len(answers) - 1
    )


@pytest.mark.parametrize("default,options", [(True, "[Y/n]"), (False, "[y/N]")])
@pytest.mark.parametrize("answer", ["", " ", "  "])
def test_askyesno_default(mocker, default, options, answer):
    inputmock = mocker.patch("dandi.support.ui.input", return_value=answer)
    r = askyesno("Is this OK?", default=default)
    assert r is default
    inputmock.assert_called_once_with(f"Is this OK? {options} ")


@pytest.mark.parametrize(
    "default,options,answers,output",
    [
        (True, "[Y/n]", ["q", ""], True),
        (False, "[y/N]", ["foo", "y"], True),
        (True, "[Y/n]", ["off", "  "], True),
    ],
)
def test_askyesno_default_invalids(capsys, mocker, default, options, answers, output):
    answeriter = iter(answers)
    inputmock = mocker.patch(
        "dandi.support.ui.input", side_effect=lambda _: next(answeriter)
    )
    r = askyesno("Is this OK?", default=default)
    assert r == output
    assert inputmock.call_args_list == [mocker.call(f"Is this OK? {options} ")] * len(
        answers
    )
    assert capsys.readouterr().out == "Please answer 'y'/'yes'/'n'/'no'.\n" * (
        len(answers) - 1
    )
