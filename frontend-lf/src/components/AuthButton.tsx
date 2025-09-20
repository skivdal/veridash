import { useAccount } from "jazz-tools/react";
import { betterAuthClient } from "../lib/authClient";
import { useIsAuthenticated } from "jazz-tools/react";

export function AuthButton() {
  const { me, logOut } = useAccount();
  const isAuthenticated = useIsAuthenticated();

  function handleLogOut() {
    logOut();
    window.history.pushState({}, "", "/");
  }
  
  async function handleSignUp() {
    await betterAuthClient.signUp.email(
      {
        email: "email1@example.com",
        password: "password",
        name: "John Doe",
      },
      {
        onSuccess: async () => {
          // Don't forget to update the profile's name. It's not done automatically.
          if (me?.profile) {
            me.profile.$jazz.set("name", "John Doe");
          }
        },
      }
    );
  }
  
  async function handleSignIn() {
    await betterAuthClient.signIn.email({
      email: "email1@example.com",
      password: "password",
    });
  }

  if (isAuthenticated) {
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
        onClick={handleSignUp}
      >
        Sign up
      </button>
      <button
        onClick={handleSignIn}
      >
        Log in
      </button>
    </div>
  );
}

