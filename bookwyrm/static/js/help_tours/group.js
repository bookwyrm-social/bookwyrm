export const steps = [
    {
        text: gettext("This is the home page for a group. Users can be added to a group, and then curate book lists together. Currently groups do not federate to other BookWyrm or Fediverse instances, but we have plans for that as well as other features in the future."),
        title: gettext('Groups'),
    },
    {
        text: gettext("Here is the name and manager of this group. Every group has a manager who can add and remove users."),
        title: gettext('About the group'),
        attachTo: {
            element: "#group-details",
            on: "bottom",
        }
    },
    {
        text: gettext("You can see group members here. If you are the manager of the group, this is also where you can search for users and invite them to join your group."),
        title: gettext('Members'),
        attachTo: {
            element: "#group-members",
            on: "bottom",
        }
    },
    {
        text: gettext("Book lists can be curated by a group rather than a single user. When you select a group to curate a list, the list appears on the group home page here."),
        title: gettext('Group lists'),
        attachTo: {
            element: "#group-lists",
            on: "top",
        }
    }
]