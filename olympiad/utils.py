def adjusted_int_name(number,size=2):
    name = str(number)
    while len(name) < size:
        name = '0' + name
    return name