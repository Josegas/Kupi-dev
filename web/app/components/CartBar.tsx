"use client";
import { useState } from "react";
import { ShoppingCart, ChevronUp, ChevronDown, X, Trash2 } from "lucide-react";
import { useCart, CartItem } from "../lib/cart";
import { useLang } from "../lib/i18n";

interface Props {
  onCompare: () => void;
  loading?: boolean;
}

export default function CartBar({ onCompare, loading }: Props) {
  const { items, removeItem, clearCart, itemCount, subtotal } = useCart();
  const { t } = useLang();
  const [expanded, setExpanded] = useState(false);

  if (itemCount === 0) return null;

  const cartT = t.cart;

  return (
    <div className="fixed bottom-0 left-0 right-0 z-40 bg-[var(--surface)] border-t border-[var(--border)] shadow-[0_-4px_20px_rgba(0,0,0,0.08)]">
      <div className="max-w-6xl mx-auto px-4 sm:px-6">
        {/* Expanded: item list */}
        {expanded && (
          <div className="py-3 border-b border-[var(--border)] max-h-48 overflow-y-auto">
            <div className="flex items-center justify-between mb-2">
              <span className="text-sm font-semibold text-[var(--text-primary)]">
                {cartT.title} ({itemCount})
              </span>
              <button
                onClick={clearCart}
                className="flex items-center gap-1 text-xs text-[var(--text-muted)] hover:text-[var(--brand)] transition-colors"
              >
                <Trash2 size={12} />
                {cartT.clear}
              </button>
            </div>
            {items.map((item, i) => (
              <div key={i} className="flex items-center justify-between py-1.5 gap-2">
                <span className="text-sm text-[var(--text-primary)] truncate flex-1">
                  {item.name}
                </span>
                <span className="text-sm font-medium text-[var(--text-secondary)] whitespace-nowrap">
                  ${item.price.toFixed(2)}
                </span>
                <button
                  onClick={() => removeItem(i)}
                  className="p-1 text-[var(--text-muted)] hover:text-[var(--brand)] transition-colors"
                >
                  <X size={14} />
                </button>
              </div>
            ))}
          </div>
        )}

        {/* Main bar */}
        <div className="flex items-center gap-3 py-3">
          <button
            onClick={() => setExpanded(!expanded)}
            className="flex items-center gap-2 flex-1 min-w-0"
          >
            <div className="relative">
              <ShoppingCart size={20} className="text-[var(--brand)]" />
              <span className="absolute -top-1.5 -right-2 bg-[var(--brand)] text-white text-[10px] font-bold w-4 h-4 rounded-full flex items-center justify-center">
                {itemCount}
              </span>
            </div>
            <div className="text-left min-w-0">
              <span className="text-sm font-semibold text-[var(--text-primary)]">
                {cartT.title}
              </span>
              <span className="text-xs text-[var(--text-muted)] ml-2">
                ${subtotal.toFixed(2)}
              </span>
            </div>
            {expanded ? <ChevronDown size={16} className="text-[var(--text-muted)]" /> : <ChevronUp size={16} className="text-[var(--text-muted)]" />}
          </button>

          <button
            onClick={onCompare}
            disabled={loading}
            className="kupi-btn px-4 py-2.5 rounded-xl text-white text-sm font-bold whitespace-nowrap disabled:opacity-50"
            style={{ backgroundColor: "var(--savings)", boxShadow: "0 4px 12px rgba(21,128,61,0.25)" }}
          >
            {loading
              ? "..."
              : `${cartT.compareN} (${itemCount})`}
          </button>
        </div>
      </div>
    </div>
  );
}
