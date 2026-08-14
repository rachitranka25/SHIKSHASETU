export const SkipLink = ({ href }: { href: string }) => {
  return (
    <a
      href={href}
      className="sr-only focus:not-sr-only focus:absolute focus:z-50 focus:p-4 focus:bg-white focus:text-black focus:top-0 focus:left-0"
    >
      Skip to content
    </a>
  );
};
