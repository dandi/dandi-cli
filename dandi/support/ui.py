def askyesno(question, default=None):
    if default is None:
        options = "[y/n]"
    elif default:
        options = "[Y/n]"
    else:
        options = "[y/N]"
    while True:
        answer = input(f"{question} {options} ").strip().lower()
        if answer in ("y", "yes"):
            return True
        elif answer in ("n", "no"):
            return False
        elif not answer and default is not None:
            return default
        else:
            print("Please answer 'y'/'yes'/'n'/'no'.")
