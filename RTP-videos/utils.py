class Queue:
    def __init__(self, capacity):
        self.capacity = capacity
        self.size = 0
        self.head = 0
        self.tail = 0
        self.arr = [float('nan')] * self.capacity


    def isEmpty(self):
        return self.size == 0


    def isFull(self):
        return self.size == self.capacity


    def getSize(self):
        return self.size


    def push(self, x):
        if self.isFull():
            return -1
        else:
            self.arr[self.tail] = x
            self.tail = (self.tail + 1) % self.capacity
            self.size += 1
            return self.size


    def pop(self):
        if self.isEmpty():
            return
        else:
            elem = self.arr[self.head]
            self.head = (self.head + 1) % self.capacity
            self.size -= 1
            return elem


class Node:
    def __init__(self, data):
        self.next = None
        self.data = data


class LinkList:
    def __init__(self):
        self.head = None
        self.tail = None
        self.size = 0


    def push(self, x):
        if self.size == 0:
            self.head = Node(x)
            self.tail = self.head
            self.size += 1
        else:
            new_node = Node(x)
            self.tail.next = new_node
            self.tail = new_node
            self.size += 1


    def pop(self):
        if self.size == 0:
            return
        elif self.size == 1:
            data = self.head.data
            self.head = self.tail = None
            self.size -= 1
            return data
        else:
            data = self.head.data
            self.head = self.head.next
            self.size -= 1
            return data


    def len(self):
        return self.size
