#pragma GCC optimize("O3,unroll-loops")
#pragma GCC target("avx2,bmi,bmi2,popcnt,lzcnt")   // اگر processors قدیمی است، این خط را commented کنید
#include <bits/stdc++.h>
using namespace std;

/*
================================================================================
 fghh — Professional Competitive Programming Template (C++17)
--------------------------------------------------------------------------------
ویژگی‌ها:
  • Fast I/O Security (اصلاح باگ سمی-colon در macro قبلی)
  • ModInt 템پلیتی دقت‌پذیر برای عملیات ماڈیولی
  • فاکتوریل و nCr/nPr با محاسبه قبلی O(1)
  • Fenwick (BIT) و Segment Tree برای پرس‌وجوهای بازه‌ای
  • DSU (Disjoint Set Union)
  • BFS / DFS بر روی لیست مجاورت
  • Dijkstra (مسیر کوتاه‌ترین با وزن غیرمنفی)
  • Floyd–Warshall (همه به همه)
  • Sieve of Eratosthenes + کوچک‌ترین فاکتور prima (SPF)
  • modpow و modinv دقیق
  • KMP Prefix Function برای جستجوی الگو
  • ساختار solve() با پشتیبانی از چند تست و ورودی/خروجی فایل برای تست محلی
================================================================================
*/

using i64  = long long;
using u64  = unsigned long long;
using i128 = __int128;
using f80  = long double;

using pii  = pair<int, int>;
using pll  = pair<i64, i64>;
using vi   = vector<int>;
using vll  = vector<i64>;
using vvi  = vector<vi>;
using vvll = vector<vll>;
using vpii = vector<pii>;
using vpll = vector<pll>;

constexpr i64  MOD   = 1'000'000'007LL;
constexpr i64  INF   = 4'000'000'000'000'000'000LL;
constexpr f80  EPS   = 1e-9L;
constexpr int  LOG   = 30;
constexpr int  MAXN  = 200'005;

inline void fast_io() {
    ios::sync_with_stdio(false);
    cin.tie(nullptr);
    cout.tie(nullptr);
}

inline void local_files(const string& in = "input.txt", const string& out = "output.txt") {
    #ifndef ONLINE_JUDGE
    freopen(in.c_str(), "r", stdin);
    freopen(out.c_str(), "w", stdout);
    #endif
}

template<i64 Mod>
struct ModInt {
    i64 x;
    ModInt() : x(0) {}
    ModInt(i64 v) { x = ((v % Mod) + Mod) % Mod; }
    ModInt& operator+=(const ModInt& o) { x += o.x; if (x >= Mod) x -= Mod; return *this; }
    ModInt& operator-=(const ModInt& o) { x -= o.x; if (x < 0) x += Mod; return *this; }
    ModInt& operator*=(const ModInt& o) { x = (x * o.x) % Mod; return *this; }
    ModInt& operator/=(const ModInt& o) { *this *= o.inv(); return *this; }
    ModInt operator+(const ModInt& o) const { ModInt r = *this; r += o; return r; }
    ModInt operator-(const ModInt& o) const { ModInt r = *this; r -= o; return r; }
    ModInt operator*(const ModInt& o) const { ModInt r = *this; r *= o; return r; }
    ModInt operator/(const ModInt& o) const { ModInt r = *this; r /= o; return r; }
    ModInt operator-() const { ModInt r; r.x = (x == 0 ? 0 : Mod - x); return r; }
    bool operator==(const ModInt& o) const { return x == o.x; }
    bool operator!=(const ModInt& o) const { return x != o.x; }
    i64 val() const { return x; }
    ModInt pow(i64 b) const {
        ModInt a = *this, r(1);
        while (b > 0) {
            if (b & 1) r *= a;
            a *= a;
            b >>= 1;
        }
        return r;
    }
    ModInt inv() const { return pow(Mod - 2); }
};

using Mint = ModInt<MOD>;

struct Comb {
    vector<Mint> fact, invFact;
    Comb(int n = MAXN) : fact(n), invFact(n) {
        fact[0] = 1;
        for (int i = 1; i < n; ++i) fact[i] = fact[i - 1] * i;
        invFact[n - 1] = fact[n - 1].inv();
        for (int i = n - 2; i >= 0; --i) invFact[i] = invFact[i + 1] * (i + 1);
    }
    Mint nCr(int n, int r) const {
        if (r < 0 || r > n) return 0;
        return fact[n] * invFact[r] * invFact[n - r];
    }
    Mint nPr(int n, int r) const {
        if (r < 0 || r > n) return 0;
        return fact[n] * invFact[n - r];
    }
};

i64 gcd(i64 a, i64 b) { while (b) { a %= b; swap(a, b); } return a; }
i64 lcm(i64 a, i64 b) { return a / gcd(a, b) * b; }

i64 modpow(i64 a, i64 b, i64 mod = MOD) {
    i64 r = 1 % mod; a %= mod; if (a < 0) a += mod;
    while (b > 0) {
        if (b & 1) r = (__int128)r * a % mod;
        a = (__int128)a * a % mod;
        b >>= 1;
    }
    return r;
}

struct Sieve {
    int n;
    vi is_prime, spf, primes;
    Sieve(int n = MAXN) : n(n), is_prime(n + 1, 1), spf(n + 1) {
        is_prime[0] = is_prime[1] = 0;
        for (int i = 2; i <= n; ++i) {
            if (is_prime[i]) {
                spf[i] = i;
                primes.push_back(i);
            }
            for (int p : primes) {
                if (1LL * i * p > n) break;
                is_prime[i * p] = 0;
                spf[i * p] = p;
                if (i % p == 0) break;
            }
        }
    }
    map<i64, int> factorize(i64 x) {
        map<i64, int> f;
        while (x > 1) {
            int p = spf[x];
            int c = 0;
            while (x % p == 0) { x /= p; ++c; }
            f[p] = c;
        }
        return f;
    }
};

struct Fenwick {
    int n;
    vector<i64> bit;
    Fenwick(int n = 0) : n(n), bit(n + 1, 0) {}
    void add(int i, i64 v) { for (; i <= n; i += i & -i) bit[i] += v; }
    i64 sum(int i) const { i64 s = 0; for (; i > 0; i -= i & -i) s += bit[i]; return s; }
    i64 range(int l, int r) const { return sum(r) - sum(l - 1); }
};

struct SegTree {
    int n;
    vector<i64> t;
    SegTree(int n = 0) : n(n), t(4 * n, 0) {}
    void build(const vll& a, int v, int tl, int tr) {
        if (tl == tr) t[v] = a[tl];
        else {
            int tm = (tl + tr) / 2;
            build(a, v * 2, tl, tm);
            build(a, v * 2 + 1, tm + 1, tr);
            t[v] = t[v * 2] + t[v * 2 + 1];
        }
    }
    void build(const vll& a) { if (!a.empty()) build(a, 1, 0, (int)a.size() - 1); }
    void update(int v, int tl, int tr, int pos, i64 val) {
        if (tl == tr) t[v] = val;
        else {
            int tm = (tl + tr) / 2;
            if (pos <= tm) update(v * 2, tl, tm, pos, val);
            else update(v * 2 + 1, tm + 1, tr, pos, val);
            t[v] = t[v * 2] + t[v * 2 + 1];
        }
    }
    void update(int pos, i64 val) { if (n) update(1, 0, n - 1, pos, val); }
    i64 query(int v, int tl, int tr, int l, int r) const {
        if (l > r) return 0;
        if (tl == l && tr == r) return t[v];
        int tm = (tl + tr) / 2;
        return query(v * 2, tl, tm, l, min(r, tm)) +
               query(v * 2 + 1, tm + 1, tr, max(l, tm + 1), r);
    }
    i64 query(int l, int r) const { return n ? query(1, 0, n - 1, l, r) : 0; }
};

struct DSU {
    vi parent, rnk;
    DSU(int n = 0) : parent(n), rnk(n, 0) { iota(parent.begin(), parent.end(), 0); }
    int find(int v) { return parent[v] == v ? v : parent[v] = find(parent[v]); }
    bool unite(int a, int b) {
        a = find(a); b = find(b);
        if (a == b) return false;
        if (rnk[a] < rnk[b]) swap(a, b);
        parent[b] = a;
        if (rnk[a] == rnk[b]) ++rnk[a];
        return true;
    }
};

vi bfs(int s, const vvi& adj) {
    int n = (int)adj.size();
    vi dist(n, -1);
    queue<int> q;
    dist[s] = 0; q.push(s);
    while (!q.empty()) {
        int u = q.front(); q.pop();
        for (int v : adj[u]) {
            if (dist[v] == -1) {
                dist[v] = dist[u] + 1;
                q.push(v);
            }
        }
    }
    return dist;
}

void dfs(int u, const vvi& adj, vi& vis) {
    vis[u] = 1;
    for (int v : adj[u]) if (!vis[v]) dfs(v, adj, vis);
}

vector<i64> dijkstra(int src, const vector<vector<pll>>& adj) {
    int n = (int)adj.size();
    vector<i64> dist(n, INF);
    priority_queue<pll, vector<pll>, greater<pll>> pq;
    dist[src] = 0;
    pq.push({0, src});
    while (!pq.empty()) {
        auto [d, u] = pq.top(); pq.pop();
        if (d > dist[u]) continue;
        for (auto [v, w] : adj[u]) {
            if (dist[u] + w < dist[v]) {
                dist[v] = dist[u] + w;
                pq.push({dist[v], v});
            }
        }
    }
    return dist;
}

void floydWarshall(vector<vector<i64>>& d) {
    int n = (int)d.size();
    for (int k = 0; k < n; ++k)
        for (int i = 0; i < n; ++i)
            for (int j = 0; j < n; ++j)
                if (d[i][k] < INF && d[k][j] < INF)
                    d[i][j] = min(d[i][j], d[i][k] + d[k][j]);
}

vi prefix_function(const string& s) {
    int n = (int)s.size();
    vi pi(n, 0);
    for (int i = 1; i < n; ++i) {
        int j = pi[i - 1];
        while (j > 0 && s[i] != s[j]) j = pi[j - 1];
        if (s[i] == s[j]) ++j;
        pi[i] = j;
    }
    return pi;
}

void solve() {
    // ← کد مساله خود را اینجا بنویسید
    int n;
    if (!(cin >> n)) return;
    cout << n << "\n";
}

int main() {
    fast_io();
    local_files();          // برای تست محلی: input.txt → output.txt

    int t = 1;
    // cin >> t;             // اگر مساله چند تست-case دارد، این خط را فعال کنید
    while (t--) solve();
    return 0;
}
