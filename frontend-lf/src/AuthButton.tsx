import { useAccount, usePasskeyAuth } from "jazz-tools/react";
import { APPLICATION_NAME } from "./main";

export function AuthButton() {
  const { logOut } = useAccount();

  const auth = usePasskeyAuth({
    appName: APPLICATION_NAME,
  });

  function handleLogOut() {
    logOut();
    window.history.pushState({}, "", "/");
  }

  if (auth.state === "signedIn") {
    return (
      <button
        onClick={handleLogOut}
      >
        Log out
      </button>
    );
  }

  return (
    <div>
      <button
        onClick={() => auth.signUp("")}
      >
        Sign up
      </button>
      <button
        onClick={() => auth.logIn()}
      >
        Log in
      </button>
    </div>
  );
}

