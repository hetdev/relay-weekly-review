// Explicit loading / error / empty states.

export function LoadingState({ label }: { label: string }) {
  return (
    <div className="state-box" role="status" aria-busy="true">
      <span className="spinner" aria-hidden="true" />
      {label}
    </div>
  );
}

export function ErrorState({
  message,
  onRetry,
}: {
  message: string;
  onRetry: () => void;
}) {
  return (
    <div className="state-box error" role="alert">
      <p>{message}</p>
      <button type="button" onClick={onRetry}>
        Try again
      </button>
    </div>
  );
}

export function EmptyState({ message }: { message: string }) {
  return (
    <div className="state-box" role="status">
      {message}
    </div>
  );
}
