
n = int(input())

digits = set()

for i in range(n):
    number = input()
    for digit in number:
        digits.add(digit)

sorted_digits = sorted(digits, reverse=True)

result = "".join(sorted_digits)

print(result)
