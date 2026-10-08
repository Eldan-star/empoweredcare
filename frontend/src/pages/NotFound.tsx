import { Link, useLocation } from "react-router-dom";

const NotFound = () => {
  const { pathname } = useLocation();
  return (
    <div className="min-h-screen bg-background flex items-center">
      <div className="mx-auto max-w-xl px-6">
        <p className="label-caps mb-3">Not found</p>
        <h1 className="text-[2.5rem] leading-tight font-medium">There is no page at this address.</h1>
        <p className="num text-sm text-muted-foreground mt-3 break-all">{pathname}</p>
        <Link to="/" className="inline-block mt-8 underline underline-offset-4">
          Go to the start page
        </Link>
      </div>
    </div>
  );
};

export default NotFound;
