import { useEffect, useState } from "react";

const pathnameListeners = new Set();

function notifyPathnameChange() {
  const pathname = window.location.pathname;
  pathnameListeners.forEach((listener) => listener(pathname));
}

export function navigate(to) {
  const current = `${window.location.pathname}${window.location.search}${window.location.hash}`;
  if (current === to) return;
  window.history.pushState(null, "", to);
  notifyPathnameChange();
}

export function usePathname() {
  const [pathname, setPathname] = useState(() => window.location.pathname);

  useEffect(() => {
    const update = () => setPathname(window.location.pathname);
    pathnameListeners.add(update);
    window.addEventListener("popstate", update);
    return () => {
      pathnameListeners.delete(update);
      window.removeEventListener("popstate", update);
    };
  }, []);

  return pathname;
}

export function Link({ to, onClick, children, ...props }) {
  return (
    <a
      href={to}
      onClick={(event) => {
        onClick?.(event);
        if (
          event.defaultPrevented ||
          event.button !== 0 ||
          event.metaKey ||
          event.ctrlKey ||
          event.shiftKey ||
          event.altKey
        ) {
          return;
        }
        event.preventDefault();
        navigate(to);
      }}
      {...props}
    >
      {children}
    </a>
  );
}
