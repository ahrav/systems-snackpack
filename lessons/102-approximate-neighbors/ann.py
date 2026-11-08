"""Integer IVF-Flat teaching model. Run: python3 ann.py demo."""
import heapq
import sys


def distance(a, b):
    """Squared Euclidean distance for equal-dimensional integer vectors."""
    return sum((x - y) ** 2 for x, y in zip(a, b))


class Index:
    """Fixed-centroid IVF; original vectors retained, ties ordered by ID.

    Inputs are copied into tuples. All coordinates must be integers and every
    vector must have the same positive dimension. Query results are (distance,
    ID) pairs. Empty populations return empty results. This model is immutable.
    """
    def __init__(self, points, centroids):
        self.points = tuple(tuple(p) for p in points)
        self.centroids = tuple(tuple(c) for c in centroids)
        if not self.centroids or not self.centroids[0]:
            raise ValueError('positive centroid count and dimension required')
        self.dim = len(self.centroids[0])
        for vector in self.points + self.centroids:
            self.validate(vector)
        self.lists = [[] for _ in self.centroids]
        for i, point in enumerate(self.points):
            owner = min(range(len(self.centroids)),
                        key=lambda c: (distance(point, self.centroids[c]), c))
            self.lists[owner].append(i)

    def validate(self, vector):
        """Reject dimensions or coordinate types outside the model contract."""
        if len(vector) != self.dim or any(type(x) is not int for x in vector):
            raise ValueError('equal dimensions and integer coordinates required')

    def search(self, query, k, probes=None):
        """Return ranked pairs and candidate count; None selects exact scan.

        A positive probe count visits that many nearest centroids. Full probing
        equals exact scan because every ID is scanned once with exact scoring.
        """
        self.validate(query)
        if type(k) is not int or k < 0:
            raise ValueError('k must be a nonnegative integer')
        if probes is not None and (type(probes) is not int or
                                  not 1 <= probes <= len(self.centroids)):
            raise ValueError('probes must be in [1, centroid count]')
        if k == 0:
            return [], 0
        if probes is None:
            candidates = range(len(self.points))
        else:
            chosen = heapq.nsmallest(probes, range(len(self.centroids)),
                                    key=lambda c: (distance(query, self.centroids[c]), c))
            candidates = [i for c in chosen for i in self.lists[c]]
        return (heapq.nsmallest(k, ((distance(query, self.points[i]), i)
                                   for i in candidates)), len(candidates))


if __name__ == '__main__':
    if sys.argv[1:] != ['demo']:
        raise SystemExit('usage: python3 ann.py demo')
    index = Index([(0,), (51,)], [(0,), (100,)])
    for probes in (1, 2):
        result, _ = index.search((49,), 1, probes)
        print(probes, result[0][1], result[0][0])
