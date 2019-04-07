def process_id(x):
    if isinstance(x, int):
        return x
    return int(x.split('/')[-1])
