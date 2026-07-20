import { FounderListPage } from "@/features/founders/FounderListPage";

export default function Recommended() {
  return (
    <FounderListPage
      title="Recommended"
      description="Founders recommended by the backend associate-screen rule. Ordering is deterministic but not a hidden final score."
      recommendedOnly
      ruleExplanation="Recommended means any one of Founder, Vision & Product, Differentiation, or Traction is strictly greater than 75, or at least two of those scores are strictly greater than 50. Exact 75 and exact 50 do not qualify."
    />
  );
}
