# SEC CIK 覆盖审计

- 检查时间：2026-06-01T00:20:20+08:00
- listed_company_batch：61 行，其中 16 行有 sec_cik
- SEC 适用范围（美股/ADR/OTC）：16 行，已覆盖 16 行，缺失 0 行
- 非 SEC 交易所/本地交易所：45 行，不应强行填 SEC CIK
- company_capital_structure：72 行，其中 12 行有 sec_cik

## 交易所分布

| Exchange | Rows |
|---|---:|
| KRX | 22 |
| NASDAQ | 15 |
| BORSA ITALIANA | 5 |
| PA | 3 |
| SZSE | 2 |
| TA | 2 |
| Unknown | 2 |
| TW | 2 |
| SIX | 1 |
| HKEX | 1 |
| OTC | 1 |
| T | 1 |
| JSE | 1 |
| BR | 1 |
| TWO | 1 |
| ASX | 1 |

## SEC 适用但仍缺 CIK

当前没有 SEC 适用但缺失 CIK 的上市主体。剩余空值主要是 KRX、HKEX、SIX、欧洲、A 股等本地交易所。

## 结论

原始缺口口径会把非美国交易所也算作 SEC 缺失。按 SEC 实际适用范围看，当前 SEC CIK 覆盖为 16/16；下一步应为非美国上市主体补本地交易所/年报链接，而不是继续追 SEC CIK。
