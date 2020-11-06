def askyesno(question, default=None):
    if default is None:
        options = "[yes|no]"
    elif default:
        options = "[Yes|no]"
    else:
        options = "[yes|No]"
    while True:
        answer = input(f"{question} {options}: ").strip().lower()
        if answer in ("y", "yes"):
            return True
        elif answer in ("n", "no"):
            return False
        elif answer:
            print("Please answer 'y'/'yes'/'n'/'no'.")
        elif default is not None:
            return default
