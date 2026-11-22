
n = int(input())
m = int(input())
o = input()

results = []

for a, b in zip(range(1, n + 1), range(m - n + 1, m + 1)):
    if o == "+":
        result = a + b
    elif o == "-":
        result = a - b
    elif o == "*":
        result = a * b
    elif o == "/":
        result = a / b

    results.append(result)

average = sum(results) / len(results)
print(average)
