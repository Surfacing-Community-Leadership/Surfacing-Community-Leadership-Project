// Generic styled button, shared across the app.
export default function Button({ children, ...props }) {
  return (
    <button {...props}>{children}</button>
  );
}
