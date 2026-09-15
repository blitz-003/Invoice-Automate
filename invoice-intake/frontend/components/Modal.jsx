"use client";

export default function Modal({ open, onClose, title, children, wide, footer }) {
  if (!open) return null;
  return (
    <div className="modal-backdrop" onClick={onClose}>
      <div
        className={`modal${wide ? " wide" : ""}`}
        onClick={(e) => e.stopPropagation()}
        role="dialog"
        aria-modal="true"
        aria-label={title}
      >
        {title && <h3 className="t-title mb-md">{title}</h3>}
        <div>{children}</div>
        {footer && <div className="row between mt-lg" style={{ justifyContent: "flex-end" }}>{footer}</div>}
      </div>
    </div>
  );
}