

def get_example_data() -> list:
    import pickle
    with open("example.pkl", "rb") as file:
        data = pickle.load(file)
    return data

print(get_example_data())
