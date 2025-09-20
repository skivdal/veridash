import { betterAuth } from "better-auth";
import Database from "better-sqlite3";
import { jazzPlugin } from "jazz-tools/better-auth/auth/server";

export const auth = betterAuth({
  plugins: [
    jazzPlugin(),
  ],
  trustedOrigins: ["http://localhost:5173"],
  database: new Database("./sqlite.db"),
  databaseHooks: {
    user: {
      create: {
        async after(user) {
          // Here we can send a welcome email to the user
          console.log("User created with Jazz Account ID:", user.accountID);
        },
      },
    },
  },
  emailAndPassword: {
    enabled: true,
    requireEmailVerification: false,
  },
  emailVerification: {
    sendOnSignUp: false,
    sendVerificationEmail: async ({user, url}, _req) => {
      console.log("trying to verify user email", user, url);
    },
  }
})
