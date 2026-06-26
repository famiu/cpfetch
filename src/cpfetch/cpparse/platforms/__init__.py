"""Per-judge parser implementation modules."""

__all__ = ["AtCoderParser", "CodeChefParser", "CodeforcesParser", "CsesParser", "SpojParser"]

from .atcoder import AtCoderParser
from .codechef import CodeChefParser
from .codeforces import CodeforcesParser
from .cses import CsesParser
from .spoj import SpojParser
