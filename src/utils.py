from functools import reduce
from collections.abc import Iterator


class RatelimitException(Exception):
    pass


class Link(Iterator):
    def __new__(cls, *args, **kwargs):
        instance = super().__new__(cls)
        instance.prev_link = None
        instance.next_link = None
        return instance

    def __rshift__(self, other):
        if not isinstance(other, Link):
            raise NotImplementedError
        else:
            self.next_link = other
            other.prev_link = self
            return other

    def _get_first_link(self):
        current_link = self
        while current_link.prev_link:
            current_link = current_link.prev_link
        return current_link

    def __iter__(self):
        self._current_link = self._get_first_link()
        return self

    def __next__(self):
        while (tmp := self._current_link):
            self._current_link = self._current_link.next_link
            return tmp
        raise StopIteration

    @classmethod
    def seq(cls, *links):
        if not all(isinstance(link, Link) for link in links):
            raise NotImplementedError
        else:
            return reduce(lambda x, y: x >> y, links)

    @property
    def is_first(self):
        return not self.prev_link

    @property
    def is_last(self):
        return not self.next_link

    @property
    def is_in_middle(self):
        return not (self.is_first or self.is_last)

    @property
    def is_only_one(self):
        return self.is_first and self.is_last

    def get_placements(self):
        print(self)
        print('is only one:', self.is_only_one)
        print('is first:', self.is_first)
        print('is in middle:', self.is_in_middle)
        print('is last:', self.is_last)


class NamedLink(Link):
    def __init__(self, name):
        self.name = name

    def __str__(self):
        return self.name

# for link in (NamedLink('a') >> NamedLink('b')):
#     print(link)
