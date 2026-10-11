import axios from "axios";

export function getErrorMessage(error: unknown) {
  if (axios.isAxiosError(error)) {
    const responseData = error.response?.data;
    const nestedError = responseData?.error;

    if (typeof nestedError?.detail === "string") {
      return nestedError.detail;
    }

    if (Array.isArray(nestedError?.detail)) {
      return formatErrorItems(nestedError.detail);
    }

    if (Array.isArray(nestedError?.errors)) {
      return formatErrorItems(nestedError.errors);
    }

    if (typeof responseData?.message === "string") {
      return responseData.message;
    }

    if (typeof responseData?.detail === "string") {
      return responseData.detail;
    }

    if (Array.isArray(responseData?.detail)) {
      return formatErrorItems(responseData.detail);
    }

    if (error.response?.status === 413) {
      return "The selected files are too large to upload.";
    }

    if (error.response?.status) {
      return `Request failed (${error.response.status}).`;
    }
  }

  if (error instanceof Error) {
    return error.message;
  }

  return "Something went wrong. Try again.";
}

function formatErrorItems(items: Array<{ message?: string; msg?: string; detail?: string } | string>) {
  return items
    .map((item) =>
      typeof item === "string"
        ? item
        : item.message || item.msg || item.detail || String(item),
    )
    .join("\n");
}
