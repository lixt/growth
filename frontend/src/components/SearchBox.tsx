import { useEffect, useMemo, useState } from "react";
import type { StockSuggest } from "../api";
import { searchStocks } from "../api";

export default function SearchBox({
  onSelect
}: {
  onSelect: (stock: StockSuggest) => void;
}) {
  const [query, setQuery] = useState("");
  const [items, setItems] = useState<StockSuggest[]>([]);
  const [open, setOpen] = useState(false);

  useEffect(() => {
    if (!query.trim()) {
      setItems([]);
      return;
    }

    const t = setTimeout(async () => {
      const data = await searchStocks(query);
      setItems(data);
      setOpen(true);
    }, 250);

    return () => clearTimeout(t);
  }, [query]);

  const placeholder = useMemo(() => "输入股票名 / 拼音 / 代码", []);

  return (
    <div className="search">
      <input
        value={query}
        onChange={(e) => setQuery(e.target.value)}
        placeholder={placeholder}
        onFocus={() => setOpen(true)}
        onKeyDown={(e) => {
          if (e.key === "Enter" && items[0]) {
            onSelect(items[0]);
            setOpen(false);
          }
        }}
      />
      {open && items.length > 0 && (
        <div className="suggest">
          {items.map((it) => (
            <div
              key={it.ts_code}
              className="suggest-item"
              onClick={() => {
                onSelect(it);
                setOpen(false);
                setQuery(`${it.name || ""} ${it.ts_code}`.trim());
              }}
            >
              <div className="suggest-name">{it.name || "-"}</div>
              <div className="suggest-meta">
                {it.ts_code} {it.cnspell ? `· ${it.cnspell}` : ""}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
