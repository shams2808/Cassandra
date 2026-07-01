export async function fetchUserData(userId) {
  // Line comment with { braces } inside it
  const url = `/api/users/${userId}`;
  const response = await fetch(url);
  /* Block comment
     with { braces }
  */
  return response.json();
}

const config = {
  // Arrow function assigned to object property
  logger: (msg) => {
    console.log(`[LOG]: ${msg}`);
  },
  endpoint: "https://api.example.com"
};

class UserManager {
  constructor(provider) {
    this.provider = provider;
  }

  async verifyUser(token) {
    const isValid = token === "valid-token";
    if (isValid) {
      console.log("Token verified successfully.");
    }
    return isValid;
  }
}
