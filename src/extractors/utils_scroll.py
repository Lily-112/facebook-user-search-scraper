from typing import Callable, List, Any

class ScrollPaginator:
    """
    A small utility that mimics infinite-scroll pagination by repeatedly
    calling a provided fetch(page_index) function.
    """

    def __init__(self, fetch: Callable[[int], Any]):
        self.fetch = fetch

    def collect_pages(self, scrolls: int) -> List[Any]:
        pages: List[Any] = []
        for i in range(max(1, int(scrolls))):
            pages.append(self.fetch(i))
        return pages