import { useAccount, useIsAuthenticated } from "jazz-tools/react";

export function AuthStateIndicator() {
  const { agent } = useAccount();
  const isAuthenticated = useIsAuthenticated();

  // Check if guest mode is enabled in JazzReactProvider
  const isGuest = agent._type !== "Account"

  // Anonymous authentication: has an account but not fully authenticated
  const isAnonymous =  agent._type === "Account" && !isAuthenticated;
  return (
    <div>
      {isGuest && <span>Guest Mode</span>}
      {isAnonymous && <span>Anonymous Account</span>}
      {isAuthenticated && <span>Authenticated</span>}
    </div>
  );
}

