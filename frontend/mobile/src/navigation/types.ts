import type { NavigatorScreenParams } from "@react-navigation/native";

/** The static legal pages; the register checkbox links to them. */
export type LegalDocument = "privacy" | "terms";

export type MainTabParamList = {
  CustomerHome: undefined;
  CustomerChats: undefined;
  CustomerAIChat: undefined;
  CustomerBookings: undefined;
  ProviderHome: undefined;
  ProviderSchedule: undefined;
  ProviderBookings: undefined;
  ProviderChats: undefined;
  AdminDashboard: undefined;
  Account: undefined;
};

export type RootStackParamList = {
  Auth: undefined;
  VerifyEmail: undefined;
  Legal: {
    document: LegalDocument;
  };
  Main: NavigatorScreenParams<MainTabParamList> | undefined;
  CustomerProviderDetail: {
    providerId: number;
    providerTag?: string;
  };
  CustomerProviderSearchResults: {
    keyword: string;
    serviceProvince: string;
    serviceLocationId?: number;
    serviceAreaLabel?: string;
    category?: string;
  };
  CustomerProviderPortfolioDetail: {
    providerId: number;
    portfolioId: number;
  };
  ChatRoom: {
    chatRoomId: number;
    title: string;
    opponentOnline?: boolean;
    providerProfileId?: number;
  };
  AccountEdit: undefined;
  ProviderVerification: undefined;
  ProviderIdentityVerification: undefined;
  ProviderServiceVerification: undefined;
  ProviderPayoutAccount: undefined;
  ProviderOperatingSettings: undefined;
  AccountSecurity: undefined;
  Help: undefined;
  BookingHistory: undefined;
  Notifications: undefined;
  NotificationSettings: undefined;
  Payments: undefined;
  PaymentResult: {
    booking_id?: string;
    payment_status?: string;
  };
  CustomerFavourites: undefined;
  ProviderPortfolioList: undefined;
  ProviderPortfolioCreate: undefined;
  ProviderPortfolioDetail: {
    portfolioId: number;
  };
};
