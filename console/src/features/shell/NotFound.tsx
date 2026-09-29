import { Compass } from "lucide-react";
import { useNavigate } from "react-router";
import { Button } from "@/design/components/Button";
import { EmptyState } from "@/design/components/Surface";

export default function NotFound() {
  const navigate = useNavigate();
  return (
    <div className="grid min-h-[70vh] place-items-center px-6">
      <EmptyState
        icon={<Compass />}
        title="This page doesn’t exist"
        message="The address may be mistyped, or the page may have moved."
        action={
          <Button variant="filled" onClick={() => navigate("/")}>
            Go to Overview
          </Button>
        }
      />
    </div>
  );
}
