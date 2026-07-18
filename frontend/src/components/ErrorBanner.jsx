export default function ErrorBanner({ message }) {
  if (!message) return null;
  return (
    <div className="w-full text-sm text-maroon  border-maroon/20 rounded-lg px-4 py-2.5">
      {message}
    </div>
  );
}