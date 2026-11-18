def get_int_param(params, name, default=None):
    """GET/POST параметрийг int болгож буцаана.

    Байхгүй эсвэл тоо биш утга (жишээ нь сканнерын '63 ORDER BY 1-- -') ирвэл
    `default`-ийг буцаана — ORM-д string дамжуулж ValueError → 500 гаргахаас сэргийлнэ.
    """
    value = params.get(name)
    if value is None or value == '':
        return default
    try:
        return int(str(value).strip())
    except (TypeError, ValueError):
        return default
