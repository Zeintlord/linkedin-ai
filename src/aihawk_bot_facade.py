class AIHawkBotFacade:
    def __init__(self, authenticator, job_manager):
        self.authenticator = authenticator
        self.job_manager = job_manager
        self.resume_data = None
        self.parameters = None

    def set_resume_data(self, resume_data):
        self.resume_data = resume_data

    def set_parameters(self, parameters):
        self.parameters = parameters

    def start_login(self):
        self.authenticator.start_login()

    def start_apply(self):
        if self.resume_data:
            self.job_manager.apply_to_jobs(self.resume_data)
