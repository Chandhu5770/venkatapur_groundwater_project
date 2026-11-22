
numbers = list(map(int, input().split()))
T = int(input())

result = "Foo"

for i in range(len(numbers)):
    if numbers[i] >= T:
        result = i
        break

print(result)
