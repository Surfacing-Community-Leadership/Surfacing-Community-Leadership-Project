import { useState } from "react";

// Replaces the browser's native confirm()/prompt() with in-app modals.

function ModalShell({ title, children, onClose }) {
  return (
    <div className="modal-backdrop" onClick={onClose}>
      <div className="modal card" onClick={(e) => e.stopPropagation()}>
        <h2>{title}</h2>
        {children}
      </div>
    </div>
  );
}

export function ConfirmDialog({ open, title, body, confirmLabel = "Confirm", danger, onConfirm, onClose }) {
  if (!open) return null;
  return (
    <ModalShell title={title} onClose={onClose}>
      <p>{body}</p>
      <div className="row-actions">
        <button className="secondary" onClick={onClose}>
          Cancel
        </button>
        <button className={danger ? "danger" : ""} onClick={onConfirm}>
          {confirmLabel}
        </button>
      </div>
    </ModalShell>
  );
}

export function ReportDialog({ open, what, onSubmit, onClose }) {
  const [reason, setReason] = useState("");
  if (!open) return null;

  function submit(e) {
    e.preventDefault();
    onSubmit(reason);
    setReason("");
  }

  return (
    <ModalShell title={`Report ${what}`} onClose={onClose}>
      <form onSubmit={submit}>
        <p className="muted">
          Tell the moderators what's wrong. Reports are confidential.
        </p>
        <textarea
          value={reason}
          onChange={(e) => setReason(e.target.value)}
          rows={3}
          maxLength={200}
          required
          placeholder="Reason…"
          autoFocus
        />
        <div className="row-actions">
          <button type="button" className="secondary" onClick={onClose}>
            Cancel
          </button>
          <button type="submit">Send report</button>
        </div>
      </form>
    </ModalShell>
  );
}
