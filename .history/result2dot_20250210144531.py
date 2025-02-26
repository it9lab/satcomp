
with open('csdot', 'r') as file:
    data = file.read()

data_dict = json.loads(data)
print(data_dict)