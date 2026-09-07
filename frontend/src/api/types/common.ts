export type PageParams = {
  page?: number;
  page_size?: number;
};

export type OffsetParams = {
  skip?: number;
  limit?: number;
};

export type Page<T> = {
  items: T[];
  page: number;
  page_size: number;
  total: number;
  pages: number;
};

export type MessageResponse = {
  message: string;
  preview_token?: string;
};
